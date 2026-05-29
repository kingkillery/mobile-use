"""Verifier helper for SkillOpt mobile-use episodes."""

from __future__ import annotations

import ast
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Score:
    passed: bool
    soft: float
    reason: str


def run_verifier(item: dict, trace_path: Path) -> Score:
    command = item["verifier_command"]
    command = command.format(trace_path=trace_path)
    if "{trace_path}" not in item["verifier_command"]:
        command = f"{command} {trace_path}"

    proc = subprocess.run(
        command.split(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    raw = proc.stdout.strip()
    if not raw:
        return Score(passed=False, soft=0.0, reason="Verifier output was empty")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            data = ast.literal_eval(raw)
        except Exception:
            return Score(passed=False, soft=0.0, reason=f"Unable to parse verifier output: {raw}")
    return Score(
        passed=bool(data.get("passed", False)),
        soft=float(data.get("soft", 0.0)),
        reason=str(data.get("reason", "")),
    )
