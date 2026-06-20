"""Run a lightweight SkillOpt-style optimization loop for mobile-use skills."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml

from benchmarks.mobileuse import run_benchmark


ROOT_DIR = Path(__file__).resolve().parents[2]


@dataclass
class EvalSummary:
    split: str
    hard: int
    total: int
    soft: float

    @property
    def hard_rate(self) -> float:
        return self.hard / self.total if self.total else 0.0


def _load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _score(results: list[dict]) -> EvalSummary:
    total = len(results)
    hard = sum(1 for item in results if item.get("hard") == 1)
    soft = sum(float(item.get("soft", 0.0)) for item in results)
    return EvalSummary(split="", hard=hard, total=total, soft=soft / total if total else 0.0)


def _summarize_failures(results: list[dict], top_k: int = 5) -> list[str]:
    failed = [
        {
            "id": item["id"],
            "reason": str(item.get("fail_reason") or ""),
            "steps": int(item.get("steps", 0) or 0),
        }
        for item in results
        if item.get("hard") != 1
    ]
    failed.sort(key=lambda f: f["steps"], reverse=True)
    return [f"{failure['id']}: {failure['reason']}" for failure in failed[:top_k]]


def _read_skill(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _propose_candidate(
    current_skill: str,
    failures: list[str],
    model: str,
    attempt: int,
    split: str,
) -> str:
    prompt = (
        "You are optimizing a mobile-use prompt appendix for Cortex.\n"
        "Goal: improve task success on Android settings/calculator style benchmarks.\n"
        "Instructions:\n"
        "- Return only markdown content for the learned skill body.\n"
        "- Keep instructions short, deterministic, and action-oriented.\n"
        "- Prefer retries and explicit app-reentry steps after failed navigation.\n"
        "- Keep outputs under 400 words.\n\n"
        f"Current learned skill:\n{current_skill.strip()}\n\n"
        f"Recent failures from {split}:\n"
        + "\n".join(f"- {item}" for item in failures)
        + "\n\nReturn the full replacement skill markdown text only."
        + f" (attempt {attempt})"
    )

    proc = subprocess.run(
        ["llm", "-m", model, prompt],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"llm proposal failed (attempt={attempt}): {proc.stderr.strip()}")
    return proc.stdout.strip()


def _run_split(split_name: str, skill_path: Path | None, output_dir: Path) -> list[dict]:
    items_path = {
        "train": "benchmarks/mobileuse/train/items.json",
        "val": "benchmarks/mobileuse/val/items.json",
        "test": "benchmarks/mobileuse/test/items.json",
    }[split_name]

    return asyncio.run(
        run_benchmark.run_split(
            items_path=ROOT_DIR / items_path,
            skill_path=str(skill_path) if skill_path else None,
            traces_root=output_dir / "traces",
        )
    )


def _safe_frontmatter(
    text: str,
    target: str,
    baseline_score: float,
    val_score: float,
    test_score: float,
) -> str:
    meta = {
        "target": target,
        "trained_on": "benchmarks/mobileuse",
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "baseline_score": f"{baseline_score:.2f}",
        "val_score": f"{val_score:.2f}",
        "test_score": f"{test_score:.2f}",
    }
    block = ["---"]
    for key, value in meta.items():
        block.append(f"{key}: {value}")
    block.append("---\n")
    return "\n".join(block) + text.lstrip("\n")


def _append_report(output_path: Path, row: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_candidate(
    skill_text: str,
    epoch: int,
    candidate_idx: int,
    output_dir: Path,
    target: str,
    baseline_score: float,
    val_score: float,
    test_score: float,
) -> Path:
    filename = f"mobileuse-cortex-v{epoch:03d}-i{candidate_idx:02d}.md"
    path = output_dir / filename
    payload = _safe_frontmatter(
        skill_text,
        target=target,
        baseline_score=baseline_score,
        val_score=val_score,
        test_score=test_score,
    )
    _write_text(path, payload)
    return path


def run_loop(
    config: dict,
    output_dir: Path,
    skill_path: Path | None,
    model: str,
    dry_run: bool = False,
) -> dict:
    workers = int(config.get("workers", 1))
    batch_size = int(config.get("batch_size", 1))
    num_epochs = int(config.get("num_epochs", 1))
    default_skill_path = Path(config.get("mobileuse", {}).get("skill_path", config["skill_path"] if "skill_path" in config else "optimized-skills/best_skill.md"))

    if workers != 1:
        raise RuntimeError("Optimization runner currently supports workers=1 only")

    current_skill_path = skill_path or default_skill_path
    current_skill = _read_skill(current_skill_path)

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        baseline_train: list[dict] = []
        baseline_summary = EvalSummary(split="train", hard=0, total=0, soft=0.0)
    else:
        baseline_train = _run_split("train", current_skill_path, output_dir)
        baseline_summary = _score(baseline_train)
        _write_text(output_dir / "train_baseline.json", json.dumps(baseline_train, indent=2))

    best_skill = current_skill
    baseline_train_size = max(1, len(baseline_train))
    best_hard = baseline_summary.hard
    best_soft = baseline_summary.soft
    best_path = current_skill_path

    for epoch in range(1, num_epochs + 1):
        if dry_run:
            break

        epoch_dir = output_dir / f"epoch_{epoch:02d}"
        failures = _summarize_failures(baseline_train)
        candidates = []
        report_path = epoch_dir / "epoch_report.jsonl"
        epoch_dir.mkdir(parents=True, exist_ok=True)

        candidate_count = max(1, batch_size)
        for i in range(candidate_count):
            try:
                proposed = _propose_candidate(
                    current_skill=best_skill,
                    failures=failures,
                    model=model,
                    attempt=i + 1,
                    split="train",
                )
            except Exception as exc:
                proposed = best_skill
                _append_report(
                    report_path,
                    {"epoch": epoch, "candidate": i + 1, "error": str(exc)},
                )

            candidate_path = epoch_dir / f"candidate_{i+1}.md"
            _write_text(candidate_path, proposed)
            candidates.append(candidate_path)

        scored: list[tuple[Path, EvalSummary]] = []
        for candidate in candidates:
            val_results = _run_split("val", candidate, epoch_dir)
            val_summary = _score(val_results)
            scored.append((candidate, val_summary))
            _append_report(
                report_path,
                {
                    "epoch": epoch,
                    "candidate": candidate.name,
                    "val_hard": val_summary.hard_rate,
                    "val_soft": val_summary.soft,
                    "val_total": val_summary.total,
                },
            )

        scored.sort(key=lambda item: (item[1].hard, item[1].soft), reverse=True)
        top_candidate, top_summary = scored[0]

        candidate_idx = candidates.index(top_candidate) + 1
        candidate_text = _read_skill(top_candidate)
        test_results = _run_split("test", top_candidate, epoch_dir)
        test_summary = _score(test_results)
        candidate_version = _write_candidate(
            candidate_text,
            epoch=epoch,
            candidate_idx=candidate_idx,
            output_dir=output_dir,
            target=config.get("target", "cortex"),
            baseline_score=baseline_summary.hard_rate,
            val_score=top_summary.hard_rate,
            test_score=test_summary.hard_rate,
        )

        if top_summary.hard > best_hard or (
            top_summary.hard == best_hard and top_summary.soft > best_soft
        ):
            best_skill = candidate_text
            best_path = candidate_version
            best_hard = top_summary.hard
            best_soft = top_summary.soft
            baseline_train = _run_split("train", candidate_version, epoch_dir)
            baseline_summary = _score(baseline_train)
            baseline_train_size = max(1, len(baseline_train))
            _append_report(
                report_path,
                {
                    "epoch": epoch,
                    "selected": str(candidate_version),
                    "improved": True,
                    "best_hard_count": best_hard,
                    "best_soft": best_soft,
                },
            )
        else:
            _append_report(report_path, {"epoch": epoch, "improved": False})
            break

    final_test = []
    if not dry_run:
        final_test = _run_split("test", best_path, output_dir)
        final_summary = _score(final_test)
        _write_text(output_dir / "test_best.json", json.dumps(final_test, indent=2))
        _append_report(
            output_dir / "optimization_summary.jsonl",
            {
                "best_path": str(best_path),
                "best_hard": best_hard / (len(baseline_train) if baseline_train else 1),
                "best_soft": best_soft / len(baseline_train) if baseline_train else 0.0,
                "test_hard": final_summary.hard_rate,
                "test_soft": final_summary.soft,
            },
        )
    else:
        final_summary = EvalSummary(split="test", hard=0, total=0, soft=0.0)

    return {
        "best_path": str(best_path),
        "best_hard_rate": best_hard / baseline_train_size,
        "best_soft": best_soft,
        "test_hard_rate": final_summary.hard_rate,
        "test_soft": final_summary.soft,
        "num_epochs": len(list(range(1, num_epochs + 1))),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run mobile-use benchmark optimization loop")
    parser.add_argument(
        "--config",
        default="skillopt_mobileuse/configs/mobileuse/default.yaml",
        help="Path to optimization config",
    )
    parser.add_argument(
        "--model",
        default="openrouter/deepseek/deepseek-v4-flash",
        help="llm model for skill proposals",
    )
    parser.add_argument("--skill-path", default=None, help="Starting skill path")
    parser.add_argument(
        "--output-dir",
        default="outputs/mobileuse_opt",
        help="Output directory",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build candidates without device runs")

    args = parser.parse_args()
    config = _load_config(Path(args.config))
    result = run_loop(
        config=config,
        output_dir=Path(args.output_dir),
        skill_path=Path(args.skill_path) if args.skill_path else None,
        model=args.model,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
