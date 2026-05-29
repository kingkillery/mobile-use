"""Load benchmark items for SkillOpt mobile-use optimization."""

from __future__ import annotations

import json
from pathlib import Path


def load_items(items_path: str | Path) -> list[dict]:
    return json.loads(Path(items_path).read_text(encoding="utf-8"))
