#!/usr/bin/env python3
"""Autonomous Coin Master Board Adventure gameplay loop.

Fast loop: vision model (minimax-m3 via OpenRouter) picks one action per screenshot.
Optimizer: text-only gpt-oss-120b:nitro via OpenRouter rewrites the live strategy
file every 5 minutes so the agent improves between runs.

Safety:
- Never confirms a purchase.  Purchase modals are closed with the Android back key.
- Stops if an auth/payment/survey/identity screen appears.
- Stop-file based shutdown.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LOG = REPO_ROOT / "runtime" / "gameplay_loop.log"
DEFAULT_METRICS = REPO_ROOT / "runtime" / "gameplay_loop.metrics.json"
DEFAULT_STOP = REPO_ROOT / "runtime" / "gameplay_loop.stop"
DEFAULT_STRATEGY = REPO_ROOT / "runtime" / "gameplay_loop.strategy.json"
DEFAULT_SCREEN_DIR = REPO_ROOT / "runtime" / "gameplay_loop_screens"

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
GAME_PACKAGE = "com.moonactive.cmboard"
GAME_ACTIVITY = "com.moon.coinmaster.android.GameActivity"

DEFAULT_STRATEGY_DATA: dict[str, Any] = {
    "screen_width": 1080,
    "screen_height": 2424,
    "image_width": 480,
    "vision_model": "minimax/minimax-m3",
    "optimizer_model": "openai/gpt-oss-120b:nitro",
    "vision_max_tokens": 250,
    "optimizer_max_tokens": 1200,
    "llm_timeout_seconds": 90,
    "roll_cooldown_ms": 2800,
    "build_tap_cooldown_ms": 1800,
    "modal_close_cooldown_ms": 1200,
    "claim_cooldown_ms": 1500,
    "poll_ms": 3000,
    "effectiveness_diff_threshold": 0.006,
    "stuck_repeat_count": 3,
    "optimizer_interval_seconds": 300,
    "effectiveness_interval_seconds": 180,
    "unsafe_keywords": [
        "sign in", "log in", "subscribe", "survey", "verify identity",
        "enter password", "credit card", "billing", "payment method",
    ],
    "purchase_keywords": ["more coins", "$", "purchase", "buy", "3.99"],
    "dice_center": [540, 2180],
    "card_centers": [[108, 2137], [324, 2137], [540, 2137], [756, 2137], [972, 2137]],
    "claim_button": [640, 380],
    "purchase_close": [960, 300],
    "close_top_right": [980, 115],
    "ok_center": [540, 1450],
    "raid_holes": [[270, 900], [540, 700], [810, 900]],
    "build_open_swipe": [[540, 1800], [540, 2400]],
    "continue_button": [540, 2200],
    "back_key_for_purchase": True,
}

VISION_PROMPT = (
    "You are the fast action brain for a Coin Master Board Adventure ADB bot. "
    "Screen resolution is 1080x2424 portrait. "
    "Output ONLY JSON: {\"action\":\"<action>\",\"x\":0.0-1.0,\"y\":0.0-1.0}. "
    "Actions: roll=tap large red dice button bottom center if energy>0 and button does NOT say STOP; "
    "build=tap cheapest affordable build card when bottom build panel with green price bars is open; "
    "claim=tap visible green CLAIM button/reward scroll/checkmark; "
    "close=tap X/close/continue of a modal, especially purchase modals with $/prices or a raid result screen after bags are opened; "
    "attack=tap an unopened red raid bag/hole during attack/raid (ignore bags already showing a yellow X). "
    "Priority: 1) close $ modals and finished raid screens, 2) claim rewards, 3) build if panel open, 4) roll if energy>0, 5) attack if raid bags are available, 6) wait. "
    "Never purchase. Never tap auth/sign-in. Return JSON only."
)

OPTIMIZER_PROMPT = (
    "You are optimizing an autonomous Coin Master Board Adventure agent. "
    "Goal: reach Village 2 by earning coins (rolling dice) and buying village items for stars. "
    "Safety: never purchase, never enter auth/payment/survey/identity flows.\n\n"
    "You are given the current metrics and strategy JSON. "
    "Return ONLY a JSON object with no markdown or prose:\n"
    "{\"updated_strategy\": {...same keys...}, \"recommended_next_action\": \"roll|build|claim|close|attack|wait\", \"notes\": \"brief reasoning\"}\n\n"
    "In updated_strategy you may adjust coordinates, cooldowns, max_tokens, and thresholds. "
    "Only output keys that exist in the input strategy. Do not add new keys."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def log(msg: str, log_path: Path) -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    line = f"{stamp} {msg}"
    print(line)
    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def adb(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["adb"] + args, capture_output=True, text=True, timeout=timeout, check=False)


def tap(x: int, y: int) -> None:
    adb(["shell", "input", "tap", str(int(x)), str(int(y))])


def swipe(x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
    adb([
        "shell", "input", "swipe",
        str(x1), str(y1), str(x2), str(y2), str(duration_ms),
    ])


def back_key() -> None:
    adb(["shell", "input", "keyevent", "4"])


def capture_screen(path: Path) -> Path:
    adb(["shell", "screencap", "-p", "/sdcard/gameplay_loop_current.png"])
    adb(["pull", "/sdcard/gameplay_loop_current.png", str(path)])
    return path


def dump_ui(path: Path) -> str:
    try:
        adb(["shell", "uiautomator", "dump", "/sdcard/gameplay_loop_ui.xml"])
        adb(["pull", "/sdcard/gameplay_loop_ui.xml", str(path)])
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def encode_image(screen_path: Path, width: int) -> str:
    with Image.open(screen_path) as im:
        w, h = im.size
        scale = width / w
        resized = im.resize((width, int(h * scale)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()


def image_diff_ratio(a: Path, b: Path) -> float | None:
    try:
        with Image.open(a) as im_a, Image.open(b) as im_b:
            if im_a.size != im_b.size:
                return None
            pa = im_a.convert("RGB").getdata()
            pb = im_b.convert("RGB").getdata()
            diff = sum(1 for x, y in zip(pa, pb) if x != y)
            return diff / len(pa)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# API / models
# ---------------------------------------------------------------------------
def get_api_key() -> str:
    result = subprocess.run(
        [r"C:\Users\prest\.local\bin\llm.exe", "keys", "get", "openrouter"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip()


def openrouter_chat(
    key: str,
    model: str,
    messages: list[dict[str, Any]],
    max_tokens: int,
    timeout: int,
) -> dict[str, Any] | None:
    try:
        resp = httpx.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": model, "messages": messages, "max_tokens": max_tokens},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {"error": f"status {resp.status_code}", "body": resp.text[:500]}
        return resp.json()
    except Exception as exc:
        return {"error": str(exc)}


def extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    # Strip markdown fences
    text = text.strip()
    if text.startswith("```"):
        text = text[text.find("{") : text.rfind("}") + 1]
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def vision_decision(
    key: str,
    screen_path: Path,
    strategy: dict[str, Any],
    log_path: Path,
) -> dict[str, Any] | None:
    b64 = encode_image(screen_path, strategy["image_width"])
    prompt = strategy.get("vision_prompt", VISION_PROMPT)
    result = openrouter_chat(
        key,
        strategy["vision_model"],
        [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                ],
            }
        ],
        strategy["vision_max_tokens"],
        strategy["llm_timeout_seconds"],
    )
    if result is None or "error" in result:
        log(f"vision error: {result}", log_path)
        return None
    try:
        content = result["choices"][0]["message"]["content"]
    except Exception as exc:
        log(f"vision response parse error: {exc}", log_path)
        return None
    parsed = extract_json(content)
    log(f"vision raw={content!r} parsed={parsed}", log_path)
    return parsed


def run_optimizer(
    key: str,
    strategy: dict[str, Any],
    metrics: dict[str, Any],
    log_path: Path,
) -> dict[str, Any] | None:
    prompt = strategy.get("optimizer_prompt", OPTIMIZER_PROMPT)
    prompt += "\n\nCurrent metrics:\n" + json.dumps(metrics, indent=2, default=str)
    prompt += "\n\nCurrent strategy:\n" + json.dumps(strategy, indent=2)
    result = openrouter_chat(
        key,
        strategy["optimizer_model"],
        [{"role": "user", "content": prompt}],
        strategy["optimizer_max_tokens"],
        strategy["llm_timeout_seconds"],
    )
    log(f"optimizer response: {result}", log_path)
    if result is None or "error" in result:
        return None
    try:
        content = result["choices"][0]["message"]["content"]
    except Exception:
        return None
    return extract_json(content)


# ---------------------------------------------------------------------------
# Strategy / metrics
# ---------------------------------------------------------------------------
def load_strategy(path: Path) -> dict[str, Any]:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            merged = DEFAULT_STRATEGY_DATA.copy()
            merged.update(data)
            return merged
        except Exception:
            pass
    return DEFAULT_STRATEGY_DATA.copy()


def save_strategy(path: Path, strategy: dict[str, Any]) -> None:
    path.write_text(json.dumps(strategy, indent=2), encoding="utf-8")


def save_metrics(metrics: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(metrics, indent=2, default=str), encoding="utf-8")


# ---------------------------------------------------------------------------
# Safety / foreground
# ---------------------------------------------------------------------------
def game_is_foreground() -> bool:
    try:
        proc = subprocess.run(
            ["adb", "shell", "dumpsys", "window"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        for line in (proc.stdout + proc.stderr).splitlines():
            if "mCurrentFocus" in line and GAME_PACKAGE in line:
                return True
    except Exception:
        pass
    return False


def launch_game() -> None:
    subprocess.run(
        ["adb", "shell", "am", "start", "-n", f"{GAME_PACKAGE}/{GAME_ACTIVITY}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def check_safety(xml: str, strategy: dict[str, Any]) -> tuple[bool, bool]:
    text = xml.lower()
    unsafe = any(kw in text for kw in strategy["unsafe_keywords"])
    purchase = any(kw.lower() in text for kw in strategy["purchase_keywords"])
    return unsafe, purchase


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------
def apply_action(
    name: str,
    rx: float,
    ry: float,
    strategy: dict[str, Any],
    metrics: dict[str, Any],
) -> None:
    w, h = strategy["screen_width"], strategy["screen_height"]
    x = int(round(rx * w))
    y = int(round(ry * h))
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))

    if name in {"roll", "build", "claim", "close", "attack"}:
        tap(x, y)
    if name == "close" and strategy.get("back_key_for_purchase"):
        back_key()

    metrics["taps"] = metrics.get("taps", 0) + 1
    if name == "roll":
        metrics["rolls"] = metrics.get("rolls", 0) + 1
    elif name == "build":
        metrics["builds"] = metrics.get("builds", 0) + 1
    elif name == "claim":
        metrics["claims"] = metrics.get("claims", 0) + 1
    elif name == "close":
        metrics["closes"] = metrics.get("closes", 0) + 1


def cooldown_for(action: str, strategy: dict[str, Any]) -> float:
    if action == "roll":
        return strategy["roll_cooldown_ms"] / 1000
    if action == "build":
        return strategy["build_tap_cooldown_ms"] / 1000
    if action == "claim":
        return strategy["claim_cooldown_ms"] / 1000
    if action == "close":
        return strategy["modal_close_cooldown_ms"] / 1000
    return strategy["poll_ms"] / 1000


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------
class GameLoop:
    def __init__(self, args: argparse.Namespace):
        self.log_path = Path(args.log)
        self.metrics_path = Path(args.metrics)
        self.stop_path = Path(args.stop_file)
        self.strategy_path = Path(args.strategy)
        self.screen_dir = Path(args.screens)
        self.screen_dir.mkdir(parents=True, exist_ok=True)
        self.strategy = load_strategy(self.strategy_path)
        self.key = get_api_key()
        if not self.key:
            raise SystemExit("OpenRouter API key not found. Run: llm keys set openrouter")

        now = time.time()
        self.metrics: dict[str, Any] = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "last_action": "start",
            "taps": 0,
            "rolls": 0,
            "builds": 0,
            "claims": 0,
            "closes": 0,
            "recoveries": 0,
            "optimizations": 0,
            "last_change_at": now,
            "last_check_at": now,
            "last_optim_at": now,
        }
        self.screen_history: list[Path] = []
        self.last_check_screen: Path | None = None
        self.prev_screen: Path | None = None
        self.prev_action = ""
        self.stuck_count = 0
        self.idle_count = 0

    def run(self) -> int:
        log("gameplay loop started", self.log_path)
        save_metrics(self.metrics, self.metrics_path)
        self.stop_path.unlink(missing_ok=True)
        try:
            while not self.stop_path.exists():
                self.iterate()
        except KeyboardInterrupt:
            log("interrupted", self.log_path)
        finally:
            log("stopped", self.log_path)
            save_metrics(self.metrics, self.metrics_path)
        return 0

    def iterate(self) -> None:
        now = time.time()
        self.strategy = load_strategy(self.strategy_path)

        if not game_is_foreground():
            log("Coin Master not in foreground; launching", self.log_path)
            launch_game()
            time.sleep(5)
            return

        screen_path = self.screen_dir / f"screen_{int(now)}.png"
        try:
            capture_screen(screen_path)
        except Exception as exc:
            log(f"capture error: {exc}", self.log_path)
            time.sleep(5)
            return

        xml_path = self.screen_dir / f"ui_{int(now)}.xml"
        xml = dump_ui(xml_path)
        unsafe, purchase = check_safety(xml, self.strategy)
        if unsafe and not purchase:
            log("UNSAFE non-purchase screen detected; stopping", self.log_path)
            self.stop_path.touch()
            return

        self.screen_history.append(screen_path)
        if len(self.screen_history) > 80:
            old = self.screen_history.pop(0)
            old.unlink(missing_ok=True)

        decision = vision_decision(self.key, screen_path, self.strategy, self.log_path)
        if decision is None:
            log("no vision decision; waiting", self.log_path)
            time.sleep(self.strategy["poll_ms"] / 1000)
            return

        action = str(decision.get("action", "wait")).strip().lower()
        if action not in {"roll", "build", "claim", "close", "attack", "wait"}:
            log(f"unknown action {action!r}; waiting", self.log_path)
            action = "wait"

        rx = float(decision.get("x", 0.5))
        ry = float(decision.get("y", 0.5))
        log(f"action={action} rx={rx:.3f} ry={ry:.3f}", self.log_path)

        if action != "wait":
            apply_action(action, rx, ry, self.strategy, self.metrics)
            self.metrics["last_action"] = action

        # Local stuck detector: same action repeatedly with no visible change
        self._update_stuck_detector(action, screen_path)

        time.sleep(cooldown_for(action, self.strategy))

        # 3-minute effectiveness check
        if now - self.metrics["last_check_at"] >= self.strategy["effectiveness_interval_seconds"]:
            self.effectiveness_check(screen_path)
            self.metrics["last_check_at"] = now

        # 5-minute optimizer
        if now - self.metrics["last_optim_at"] >= self.strategy["optimizer_interval_seconds"]:
            self.run_optimizer()
            self.metrics["last_optim_at"] = now

        save_metrics(self.metrics, self.metrics_path)

    def effectiveness_check(self, current_screen: Path) -> None:
        if self.last_check_screen is None:
            self.last_check_screen = current_screen
            self.metrics["last_change_at"] = time.time()
            return
        ratio = image_diff_ratio(self.last_check_screen, current_screen)
        log(f"effectiveness diff_ratio={ratio}", self.log_path)
        if ratio is not None and ratio < self.strategy["effectiveness_diff_threshold"]:
            log("stagnation detected; running recovery", self.log_path)
            self.run_recovery()
            self.metrics["recoveries"] += 1
        else:
            self.metrics["last_change_at"] = time.time()
        self.last_check_screen = current_screen

    def _update_stuck_detector(self, action: str, screen_path: Path) -> None:
        # Count consecutive non-progress actions (anything except roll/build/claim)
        if action in {"roll", "build", "claim"}:
            self.idle_count = 0
        else:
            self.idle_count += 1
        if self.idle_count >= self.strategy["stuck_repeat_count"]:
            log(f"idle detector {self.idle_count} non-progress actions; running recovery", self.log_path)
            self.run_recovery()
            self.metrics["recoveries"] += 1
            self.idle_count = 0
            return

        if self.prev_screen and self.prev_screen.exists() and action == self.prev_action:
            ratio = image_diff_ratio(self.prev_screen, screen_path)
            if ratio is not None and ratio < self.strategy["effectiveness_diff_threshold"]:
                self.stuck_count += 1
                log(f"stuck detector {self.stuck_count}/{self.strategy['stuck_repeat_count']} action={action} diff={ratio}", self.log_path)
                if self.stuck_count >= self.strategy["stuck_repeat_count"]:
                    log("stuck state detected; running recovery", self.log_path)
                    self.run_recovery()
                    self.metrics["recoveries"] += 1
                    self.stuck_count = 0
                    return
            else:
                self.stuck_count = 0
        self.prev_action = action
        self.prev_screen = screen_path

    def run_recovery(self) -> None:
        log("recovery: back key", self.log_path)
        back_key()
        time.sleep(0.8)
        x, y = self.strategy["close_top_right"]
        tap(x, y)
        time.sleep(0.8)
        if self.strategy.get("continue_button"):
            x, y = self.strategy["continue_button"]
            tap(x, y)
            time.sleep(0.8)
        if self.strategy.get("build_open_swipe"):
            a, b = self.strategy["build_open_swipe"]
            swipe(a[0], a[1], b[0], b[1])
            time.sleep(1.0)
        x, y = self.strategy["dice_center"]
        tap(x, y)
        log("recovery roll", self.log_path)

    def run_optimizer(self) -> None:
        rec = run_optimizer(self.key, self.strategy, self.metrics, self.log_path)
        self.metrics["optimizations"] += 1
        if not rec:
            return
        updated = rec.get("updated_strategy")
        if isinstance(updated, dict):
            # Merge conservatively: keep defaults, override with optimizer output
            merged = DEFAULT_STRATEGY_DATA.copy()
            merged.update(self.strategy)
            merged.update(updated)
            save_strategy(self.strategy_path, merged)
            self.strategy = merged
            log("strategy updated by optimizer", self.log_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coin Master Board gameplay loop")
    parser.add_argument("--log", default=str(DEFAULT_LOG))
    parser.add_argument("--metrics", default=str(DEFAULT_METRICS))
    parser.add_argument("--stop-file", default=str(DEFAULT_STOP))
    parser.add_argument("--strategy", default=str(DEFAULT_STRATEGY))
    parser.add_argument("--screens", default=str(DEFAULT_SCREEN_DIR))
    parser.add_argument("--duration", type=int, default=0)
    args = parser.parse_args(argv)

    loop = GameLoop(args)
    if args.duration > 0:
        import threading
        def stop_after():
            time.sleep(args.duration)
            loop.stop_path.touch()
        threading.Thread(target=stop_after, daemon=True).start()

    return loop.run()


if __name__ == "__main__":
    sys.exit(main())
