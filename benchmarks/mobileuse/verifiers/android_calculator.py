"""Simple calculator result verifier."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _load_steps(trace_path: Path) -> list[str]:
    steps_path = trace_path / "steps.json"
    if not steps_path.exists():
        return []

    raw = json.loads(steps_path.read_text(encoding="utf-8"))
    values = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, str):
            continue
        values.append(data)
    return values


def _extract_result(steps: list[str]) -> str | None:
    content = "\n".join(steps)
    match = re.search(r"(?i)result\\s*[:=]\\s*(-?\\d+)", content)
    if match:
        return match.group(1)
    return None


def verify(trace_path: Path, expected: str) -> tuple[bool, float, str]:
    if not trace_path.exists() or not trace_path.is_dir():
        return False, 0.0, f"trace_path missing: {trace_path}"

    steps = _load_steps(trace_path)
    if not steps:
        return False, 0.0, "No steps.json found in trace folder"

    content = "\n".join(steps)
    result = _extract_result(steps)
    if result is None:
        expected_pattern = (
            rf"(?i)(?:computed|equals|answer|result).{{0,80}}\b{re.escape(expected)}\b"
        )
        if re.search(expected_pattern, content):
            return True, 0.8, f"Expected calculator result {expected} found in trace context"
        return False, 0.0, "No calculator result found in trace"

    if result == expected:
        return True, 1.0, f"Expected calculator result {expected} found: {result}"
    return False, 0.2, f"Expected {expected} but found {result}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_path", type=Path)
    parser.add_argument("expected")
    args = parser.parse_args()
    passed, soft, reason = verify(args.trace_path, args.expected)
    print(
        json.dumps(
            {"passed": passed, "soft": soft, "reason": reason},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
