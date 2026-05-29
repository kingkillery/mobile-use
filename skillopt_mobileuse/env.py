"""Environment helpers for SkillOpt mobile-use runs."""

from __future__ import annotations

from pathlib import Path


def resolve_trace_dir(base: str | Path, item_id: str) -> Path:
    base_path = Path(base)
    base_path.mkdir(parents=True, exist_ok=True)
    return base_path / item_id
