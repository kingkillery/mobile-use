"""Skill injection helpers for mobile-use runtime prompts."""

from __future__ import annotations

import os
from pathlib import Path

from minitap.mobile_use.utils.logger import get_logger

logger = get_logger(__name__)


def _normalize_targets(raw_targets: str | None) -> set[str]:
    if not raw_targets:
        return set()
    return {target.strip().lower() for target in raw_targets.split(",") if target.strip()}


def get_skill_targets() -> set[str]:
    return _normalize_targets(os.getenv("MOBILE_USE_SKILL_TARGETS"))


def get_skill_path() -> str | None:
    skill_path = os.getenv("MOBILE_USE_SKILL_PATH")
    if not skill_path:
        return None
    return skill_path


def load_skill_markdown() -> str | None:
    skill_path = get_skill_path()
    if not skill_path:
        return None

    path = Path(skill_path)
    if not path.exists():
        logger.warning(f"Skill file not found at {path}")
        return None
    if not path.is_file():
        logger.warning(f"Skill path is not a file: {path}")
        return None

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        logger.warning(f"Skill file is empty: {path}")
    return content


def build_agent_skill_appendix(agent_name: str) -> str:
    target_agents = get_skill_targets()
    if target_agents and agent_name.lower() not in target_agents:
        return ""

    skill_content = load_skill_markdown()
    if not skill_content:
        return ""

    return "\n\n---\n\n## Learned Mobile Skill\n\n" + skill_content + "\n"
