"""Verifier for simple Android Settings-style tasks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PASS_PATTERNS = {
    "battery": [
        r"battery level\s+(?:is|:)\s*\d+%",
        r"successfully identified the battery level",
    ],
    "wifi": [
        r"(?:opened|open|on|showing).{0,80}wi-?fi.{0,40}(?:page|screen|settings)",
        r"goals completion reason:.{0,120}wi-?fi",
    ],
    "storage": [
        r"(?:opened|open|on|showing).{0,80}storage.{0,40}(?:page|screen|settings)",
        r"goals completion reason:.{0,120}storage",
    ],
    "clock": [
        r"(?:opened|open|on|showing).{0,80}(?:timer|timers|clock).{0,40}(?:page|screen)",
        r"goals completion reason:.{0,120}(?:timer|timers|clock)",
    ],
}


def _load_steps(trace_path: Path) -> list[str]:
    steps_path = trace_path / "steps.json"
    if not steps_path.exists():
        return []

    raw = json.loads(steps_path.read_text(encoding="utf-8"))
    messages = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        data = item.get("data")
        if not isinstance(data, str):
            continue
        messages.append(data)
    return messages


def _contains_expected(steps: list[str], expected: str) -> bool:
    content = " ".join(steps).lower()
    patterns = PASS_PATTERNS.get(expected.lower(), [re.escape(expected.lower())])
    return any(re.search(pattern, content, flags=re.IGNORECASE | re.DOTALL) for pattern in patterns)


def verify(trace_path: Path, expected: str) -> tuple[bool, float, str]:
    if not trace_path.exists() or not trace_path.is_dir():
        return False, 0.0, f"trace_path missing: {trace_path}"

    steps = _load_steps(trace_path)
    if not steps:
        return False, 0.0, "No steps.json found in trace folder"

    if _contains_expected(steps, expected):
        return True, 1.0, f"Observed expected signal for '{expected}' in agent trace"

    return False, 0.0, f"Could not find '{expected}' intent in trace payload"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trace_path", type=Path)
    parser.add_argument("--expected", default="generic")
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
