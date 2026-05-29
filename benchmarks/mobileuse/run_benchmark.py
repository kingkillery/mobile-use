"""Local benchmark runner for mobile-use tasks.

The runner executes task items and optionally injects a learned mobile skill via
environment variables:
  - MOBILE_USE_SKILL_PATH
  - MOBILE_USE_SKILL_TARGETS
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass
class BenchmarkItem:
    id: str
    platform: str
    goal: str
    locked_app_package: str
    reset_command: str
    verifier_command: str
    timeout_seconds: int
    max_steps: int

    @classmethod
    def from_dict(cls, value: dict) -> BenchmarkItem:
        return cls(
            id=value["id"],
            platform=value["platform"],
            goal=value["goal"],
            locked_app_package=value["locked_app_package"],
            reset_command=value["reset_command"],
            verifier_command=value["verifier_command"],
            timeout_seconds=value.get("timeout_seconds", 120),
            max_steps=value.get("max_steps", 80),
        )


def _validate_command(command: str, cwd: Path) -> bool:
    if not command:
        return True
    try:
        parts = shlex.split(command, posix=False)
    except ValueError:
        return False
    if not parts:
        return True
    exe = parts[0]
    if exe.lower() in {"powershell", "python", "uv"}:
        return True
    return shutil.which(exe) is not None or (cwd / exe).exists()


def _load_items(path: Path) -> list[BenchmarkItem]:
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [BenchmarkItem.from_dict(item) for item in payload]


def _validate_items(items: list[BenchmarkItem], cwd: Path) -> list[dict]:
    results = []
    for item in items:
        issues: list[str] = []
        if not item.id:
            issues.append("missing id")
        if not item.platform:
            issues.append("missing platform")
        if item.platform.lower() != "android":
            issues.append(f"unsupported platform: {item.platform}")
        if not item.goal:
            issues.append("missing goal")
        if not item.locked_app_package:
            issues.append("missing locked_app_package")
        if not _validate_command(item.reset_command, cwd):
            issues.append("reset command appears invalid")
        if not _validate_command(item.verifier_command, cwd):
            issues.append("verifier command appears invalid")

        results.append(
            {
                "id": item.id,
                "valid": len(issues) == 0,
                "issues": issues,
            }
        )
    return results


def _run_reset(command: str, timeout_seconds: int = 120) -> tuple[int, str, str]:
    if not command:
        return 0, "", ""
    parts = shlex.split(command, posix=False)
    proc = subprocess.run(
        parts,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        cwd=ROOT_DIR,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _run_verifier(command: str, trace_path: Path) -> tuple[bool, float, str]:
    if not command:
        return False, 0.0, "Verifier command not configured"

    has_trace_placeholder = "{trace_path}" in command
    command = command.replace("{trace_path}", str(trace_path))
    if not has_trace_placeholder:
        command = f"{command} {trace_path}"
    parts = shlex.split(command, posix=False)
    proc = subprocess.run(
        parts,
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT_DIR,
        check=False,
    )
    raw = proc.stdout.strip()
    if not raw:
        return (
            False,
            0.0,
            proc.stderr.strip() or "Verifier returned empty output",
        )
    try:
        data = json.loads(raw)
        return (
            bool(data.get("passed", False)),
            float(data.get("soft", 0.0)),
            str(data.get("reason", "")),
        )
    except Exception:
        return False, 0.0, f"Invalid verifier output: {raw[:200]}"


def _count_steps_from_thoughts(thoughts_path: Path) -> int:
    if not thoughts_path.exists():
        return 0
    raw = thoughts_path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return 0
    if isinstance(data, list):
        return len(data)
    return 0


def _find_trace_folder(trace_root: Path, task_name: str) -> Path:
    trace_root.mkdir(parents=True, exist_ok=True)
    if not trace_root.exists():
        return trace_root / task_name

    candidates = [
        p
        for p in trace_root.iterdir()
        if p.is_dir() and p.name.startswith(task_name + "_")
    ]
    if not candidates:
        return trace_root / task_name
    return max(candidates, key=lambda p: p.stat().st_mtime)


async def run_item(item: BenchmarkItem | dict, skill_path: str | None, trace_root: Path) -> dict:
    item_obj = BenchmarkItem.from_dict(item) if isinstance(item, dict) else item

    os.environ["MOBILE_USE_SKILL_TARGETS"] = "cortex"
    if not skill_path:
        os.environ.pop("MOBILE_USE_SKILL_PATH", None)
    else:
        os.environ["MOBILE_USE_SKILL_PATH"] = str(skill_path)

    reset_code, _, reset_stderr = _run_reset(
        item_obj.reset_command,
        timeout_seconds=item_obj.timeout_seconds,
    )
    if reset_code != 0:
        return {
            "id": item_obj.id,
            "hard": 0,
            "soft": 0.0,
            "fail_reason": f"reset failed: {reset_stderr or 'exit 1'}",
            "trace_path": None,
            "thoughts_path": None,
            "steps": 0,
        }

    run_dir = trace_root
    run_name = item_obj.id

    fail_reason = ""
    task_failed = False
    from minitap.mobile_use.sdk.agent import Agent

    agent = Agent()
    try:
        await agent.init()
        task_request = (
            agent.new_task(item_obj.goal)
            .with_name(run_name)
            .with_locked_app_package(item_obj.locked_app_package)
            .with_max_steps(item_obj.max_steps)
            .with_trace_recording(True, str(run_dir))
            .with_thoughts_output_saving(str(run_dir / item_obj.id / "thoughts.json"))
        )
        await asyncio.wait_for(
            agent.run_task(request=task_request.build()),
            timeout=item_obj.timeout_seconds,
        )
    except TimeoutError:
        fail_reason = f"Task timeout after {item_obj.timeout_seconds}s"
        task_failed = True
    except Exception as exc:
        fail_reason = f"task failed: {exc}"
        task_failed = True
    finally:
        await agent.clean()

    trace_path = _find_trace_folder(run_dir, run_name)
    thoughts_path = run_dir / run_name / "thoughts.json"

    passed, soft, reason = _run_verifier(item_obj.verifier_command, trace_path)
    hard = 1 if passed and not task_failed else 0
    if hard == 0 and reason:
        fail_reason = reason if fail_reason == "" else f"{fail_reason}; {reason}"
    elif hard == 0:
        fail_reason = fail_reason or reason
    else:
        fail_reason = fail_reason or ""
    steps = _count_steps_from_thoughts(thoughts_path)

    return {
        "id": item_obj.id,
        "hard": hard,
        "soft": soft,
        "fail_reason": fail_reason,
        "trace_path": str(trace_path),
        "thoughts_path": str(thoughts_path),
        "steps": steps,
    }


async def run_split(items_path: Path, skill_path: str | None, traces_root: Path) -> list[dict]:
    items = _load_items(items_path)
    results = []
    for item in items:
        result = await run_item(item, skill_path=skill_path, trace_root=traces_root)
        results.append(result)
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="train", choices=["train", "val", "test"])
    parser.add_argument("--items", default="")
    parser.add_argument("--skill-path", default=None)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate benchmark items and commands only; do not connect a device.",
    )
    parser.add_argument("--trace-root", default="outputs/mobileuse_run/traces")
    parser.add_argument("--results-output", default="outputs/mobileuse_run/results.json")
    args = parser.parse_args()

    items_path = (
        Path(args.items)
        if args.items
        else ROOT_DIR / "benchmarks/mobileuse" / args.split / "items.json"
    )
    if args.validate_only:
        items = _load_items(items_path)
        results = _validate_items(items=items, cwd=ROOT_DIR)
    else:
        traces_root = Path(args.trace_root)
        results = asyncio.run(
            run_split(
                items_path=items_path,
                skill_path=args.skill_path,
                traces_root=traces_root,
            )
        )

    output_path = Path(args.results_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
