#!/usr/bin/env python3
"""One-shot mini optimizer using gpt-oss-120b:nitro via OpenRouter.

Reads the live strategy/metrics, attaches the latest screenshots, asks the model
for an updated strategy, and writes it back so the gameplay loop picks it up.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STRATEGY = REPO_ROOT / "runtime" / "gameplay_loop.strategy.json"
DEFAULT_METRICS = REPO_ROOT / "runtime" / "gameplay_loop.metrics.json"
DEFAULT_SCREEN_DIR = REPO_ROOT / "runtime" / "gameplay_loop_screens"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-120b:nitro"

PROMPT = (
    "You are a mini-optimizer for an autonomous Coin Master Board Adventure agent.\n"
    "Goal: reach Village 2 by rolling dice for coins and buying village items for stars.\n"
    "Safety: never purchase, never enter auth/payment/survey/identity flows.\n\n"
    "You are given the current strategy JSON, recent metrics, and the latest screenshots.\n"
    "Return ONLY a JSON object with no markdown or prose:\n"
    "{\"updated_strategy\": {...same keys...}, \"notes\": \"brief reasoning\"}\n\n"
    "Adjust only coordinates, cooldowns, max_tokens, thresholds, or the vision_prompt.\n"
    "Do not add new keys. Be conservative; small tweaks beat big changes."
)


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_key() -> str:
    result = subprocess.run(
        [r"C:\Users\prest\.local\bin\llm.exe", "keys", "get", "openrouter"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def encode(path: Path, width: int = 480) -> str:
    with Image.open(path) as im:
        w, h = im.size
        scale = width / w
        resized = im.resize((width, int(h * scale)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default=str(DEFAULT_STRATEGY))
    parser.add_argument("--metrics", default=str(DEFAULT_METRICS))
    parser.add_argument("--screens", default=str(DEFAULT_SCREEN_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--screenshots", type=int, default=6)
    args = parser.parse_args(argv)

    strategy_path = Path(args.strategy)
    metrics_path = Path(args.metrics)
    screen_dir = Path(args.screens)

    strategy = load_json(strategy_path)
    metrics = load_json(metrics_path)

    screens = sorted(screen_dir.glob("screen_*.png"))[-args.screenshots :]
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    content.append({"type": "text", "text": "Current strategy:\n" + json.dumps(strategy, indent=2)})
    content.append({"type": "text", "text": "Current metrics:\n" + json.dumps(metrics, indent=2)})

    log_path = REPO_ROOT / "runtime" / "gameplay_loop.log"
    if log_path.exists():
        lines = log_path.read_text(encoding="utf-8").splitlines()
        recent = "\n".join(lines[-40:])
        content.append({"type": "text", "text": "Recent log:\n" + recent})

    # gpt-oss-120b does not accept image input, so only attach screenshots for vision models.
    if "gpt-oss" not in args.model.lower():
        for screen in screens:
            b64 = encode(screen, strategy.get("image_width", 480))
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})

    key = get_key()
    if not key:
        print("No OpenRouter key found", file=sys.stderr)
        return 1

    resp = httpx.post(
        OPENROUTER_URL,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": args.model, "messages": [{"role": "user", "content": content}], "max_tokens": args.max_tokens},
        timeout=120,
    )
    if resp.status_code != 200:
        print(f"API error {resp.status_code}: {resp.text[:500]}", file=sys.stderr)
        return 1

    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    print("Raw response:")
    print(text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        print("No JSON found", file=sys.stderr)
        return 1

    rec = json.loads(text[start : end + 1])
    updated = rec.get("updated_strategy")
    if isinstance(updated, dict):
        strategy.update(updated)
        save_json(strategy_path, strategy)
        print("Strategy updated.")
    else:
        print("No strategy update provided.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
