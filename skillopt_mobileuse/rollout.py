"""Rollout contract for SkillOpt + mobile-use."""

from __future__ import annotations

from pathlib import Path

from benchmarks.mobileuse.run_benchmark import run_item as run_mobile_use
from .verifier import Score, run_verifier


async def run_item(item: dict, skill_path: str | None) -> dict:
    result = await run_mobile_use(
        item=item,
        skill_path=skill_path,
        trace_root=Path("outputs/mobileuse_run"),
    )
    trace_path = result.get("trace_path")
    if result.get("hard") == 0 or not trace_path:
        return result

    verifier_score: Score = run_verifier(item=item, trace_path=Path(trace_path))
    return {
        "id": item["id"],
        "hard": 1 if verifier_score.passed else 0,
        "soft": verifier_score.soft,
        "fail_reason": verifier_score.reason if not verifier_score.passed else "",
        "trace_path": str(trace_path),
        "thoughts_path": result["thoughts_path"],
        "steps": result["steps"],
    }


async def run_item_batch(items: list[dict], skill_path: str | None) -> list[dict]:
    results = []
    for item in items:
        results.append(await run_item(item, skill_path=skill_path))
    return results
