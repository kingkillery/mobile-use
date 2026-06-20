#!/usr/bin/env python3
"""Watchdog for the Coin Master gameplay loop.

Checks every 5 minutes that gameplay_loop.py is running and that its metrics
are still changing. If the loop died or appears stuck, it is restarted.

Usage:
    .venv\\Scripts\\python.exe scripts\\loop_watchdog.py
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil

REPO_ROOT = Path(__file__).resolve().parents[1]

LOOP_SCRIPT = REPO_ROOT / "scripts" / "gameplay_loop.py"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
STOP_FILE = REPO_ROOT / "runtime" / "gameplay_loop.stop"
METRICS_FILE = REPO_ROOT / "runtime" / "gameplay_loop.metrics.json"
LOG_FILE = REPO_ROOT / "runtime" / "loop_watchdog.log"

POLL_INTERVAL_SECONDS = 300  # 5 minutes
STALE_SECONDS = 600          # 10 minutes without metrics change => stuck


def log(msg: str) -> None:
    stamp = datetime.now(timezone.utc).isoformat()
    line = f"{stamp} {msg}"
    print(line)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def find_loop_processes() -> list[psutil.Process]:
    procs: list[psutil.Process] = []
    target_abs = str(LOOP_SCRIPT)
    target_name = LOOP_SCRIPT.name
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if not name.startswith("python"):
                continue
            cmdline = proc.info.get("cmdline") or []
            if any((target_abs in arg or target_name in arg) for arg in cmdline):
                procs.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs


def metrics_last_change_age() -> float | None:
    """Return seconds since the metrics file or its last_change_at was updated."""
    if not METRICS_FILE.exists():
        return None
    try:
        data = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
        last_change = data.get("last_change_at")
        if isinstance(last_change, (int, float)):
            return time.time() - float(last_change)
    except Exception:
        pass
    return time.time() - METRICS_FILE.stat().st_mtime


def kill_loop_processes(procs: list[psutil.Process]) -> None:
    for proc in procs:
        try:
            log(f"terminating loop pid={proc.pid}")
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    gone, alive = psutil.wait_procs(procs, timeout=10)
    for proc in alive:
        try:
            log(f"killing loop pid={proc.pid}")
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


def start_loop() -> subprocess.Popen | None:
    log(f"starting loop: {PYTHON_EXE} {LOOP_SCRIPT}")
    try:
        # Detach so the loop keeps running if the watchdog exits
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        if sys.platform != "win32":
            creationflags = 0
        return subprocess.Popen(
            [str(PYTHON_EXE), str(LOOP_SCRIPT)],
            cwd=str(REPO_ROOT),
            creationflags=creationflags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        log(f"failed to start loop: {exc}")
        return None


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    log("watchdog started")
    try:
        while True:
            if STOP_FILE.exists():
                log("stop file exists; watchdog exiting")
                return 0

            procs = find_loop_processes()
            age = metrics_last_change_age()

            if not procs:
                log("loop not running; restarting")
                start_loop()
            elif age is not None and age > STALE_SECONDS:
                log(f"loop stale (last change {age:.0f}s ago); restarting")
                kill_loop_processes(procs)
                # Remove any stale stop file left by a previous run
                STOP_FILE.unlink(missing_ok=True)
                start_loop()
            else:
                status = f"loop ok (pids={[p.pid for p in procs]}"
                if age is not None:
                    status += f", last_change={age:.0f}s ago)"
                else:
                    status += ", metrics missing)"
                log(status)

            time.sleep(POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        log("watchdog interrupted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
