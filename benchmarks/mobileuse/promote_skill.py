"""Manual promotion helper for benchmark-produced Cortex skills."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--target", type=Path, default=Path("optimized-skills/best_skill.md"))
    args = parser.parse_args()

    if not args.source.exists():
        raise FileNotFoundError(f"Source skill not found: {args.source}")
    shutil.copy2(args.source, args.target)
    print(f"Promoted {args.source} -> {args.target}")


if __name__ == "__main__":
    main()
