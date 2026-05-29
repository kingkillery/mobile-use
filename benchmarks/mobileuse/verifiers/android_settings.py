"""Verifier for simple Android Settings-style tasks."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PASS_PHRASES = {
    "battery": ["battery", "battery level"],
    "wifi": ["wi-fi", "wifi", "wireless"],
    "storage": ["storage", "memory"],
    "clock": ["clock", "alarm", "timer"],
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
    phrases = PASS_PHRASES.get(expected.lower(), [expected.lower()])
    content = " ".join(steps).lower()
    return any(phrase in content for phrase in phrases)


def verify(trace_path: Path, expected: str) -> tuple[bool, float, str]:
    if not trace_path.exists() or not trace_path.is_dir():
        return False, 0.0, f"trace_path missing: {trace_path}"

    steps = _load_steps(trace_path)
    if not steps:
        return False, 0.0, "No steps.json found in trace folder"

    if _contains_expected(steps, expected):
        return True, 1.0, f"Observed expected signal for '{expected}' in agent trace"

    # fallback heuristic for calculator-like text captured in steps
    if expected == "clock":
        if re.search(r"\balarm\b|timer", " ".join(steps), flags=re.IGNORECASE):
            return True, 0.6, "Fallback match for clock text"

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
