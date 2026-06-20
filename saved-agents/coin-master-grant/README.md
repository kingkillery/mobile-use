# Coin Master / Grant Gameplay Agent — Saved Snapshot

This is a saved snapshot of the autonomous Coin Master Board Adventure agent
built for the Grant offer. It was shut down and archived on 2026-06-19.

## Files

| File | Purpose |
|------|---------|
| `gameplay_loop.py` | Main autonomous loop: screenshot → vision model → tap → periodic optimizer. |
| `mini_optimizer.py` | One-shot strategy optimizer that rewrites `gameplay_loop.strategy.json`. |
| `loop_watchdog.py` | 5-minute watchdog that restarts the loop if it dies or stalls. |
| `gameplay_loop.strategy.json` | Last live strategy (cooldowns, coordinates, prompts, models). |
| `gameplay_agent_option_tree.md` | Option tree for user intervention when the agent has questions. |
| `gameplay-agent-instructions.md` | Original hand-off instructions for the Grant → Coin Master run. |

## How to resume

1. Connect the Pixel 9a (or target Android device) via ADB.
2. Make sure Coin Master is installed and the Grant offer is tracked.
3. Run the watchdog (it will start the loop automatically if needed):

   ```powershell
   cd C:\dev\Desktop-Projects\mobile-agents
   .venv\Scripts\python.exe saved-agents\coin-master-grant\loop_watchdog.py
   ```

   Or run the loop directly:

   ```powershell
   .venv\Scripts\python.exe saved-agents\coin-master-grant\gameplay_loop.py
   ```

4. To stop, create the stop file:

   ```powershell
   New-Item -ItemType File -Path runtime\gameplay_loop.stop -Force
   ```

## Safety rules

- Never purchase, sign in, verify identity, or enter payment info.
- Allowed actions: spin/roll, build, claim free rewards, OK, close, skip, later,
  tutorial-guided attack/raid.
- If an unsafe screen appears, the agent should dismiss it safely or stop and
  ask.

## Runtime state (active runs)

When running from the project root, live state is written to:

- `runtime/gameplay_loop.log`
- `runtime/gameplay_loop.metrics.json`
- `runtime/loop_watchdog.log`
- `runtime/gameplay_loop.strategy.json`
- `runtime/gameplay_loop_screens/`
