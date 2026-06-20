"""Manual promotion helper for benchmark-produced Cortex skills."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from datetime import date


def _inject_metadata(source_text: str, baseline_score: float, val_score: float, test_score: float) -> str:
    date_str = date.today().isoformat()
    prefix = (
        "---\n"
        "target: cortex\n"
        "trained_on: benchmarks/mobileuse\n"
        f"date: {date_str}\n"
        f"baseline_score: {baseline_score:.2f}\n"
        f"val_score: {val_score:.2f}\n"
        f"test_score: {test_score:.2f}\n"
        "---\n"
    )
    frontmatter = re.compile(r"^---\s*\n.*?\n---\s*\n?", re.S)
    if frontmatter.match(source_text):
        source_text = frontmatter.sub("", source_text, count=1).lstrip()
    else:
        source_text = source_text.lstrip()
    return prefix + source_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--target", type=Path, default=Path("optimized-skills/best_skill.md"))
    parser.add_argument("--baseline-score", type=float, default=0.0)
    parser.add_argument("--val-score", type=float, default=0.0)
    parser.add_argument("--test-score", type=float, default=0.0)
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Source skill not found: {args.source}")
    args.target.parent.mkdir(parents=True, exist_ok=True)
    payload = _inject_metadata(
        source_text=args.source.read_text(encoding="utf-8"),
        baseline_score=args.baseline_score,
        val_score=args.val_score,
        test_score=args.test_score,
    )
    args.target.write_text(payload, encoding="utf-8")
    print(f"Promoted {args.source} -> {args.target}")


if __name__ == "__main__":
    main()
