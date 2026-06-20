# Mobile Agents Index

A living index of the agents and agent-related components in this repository.

## Agents created in this session

| Agent | Script | Purpose | Status | Key runtime files |
|-------|--------|---------|--------|-------------------|
| **Coin Master / Grant Gameplay Loop** | `scripts/gameplay_loop.py` | Autonomous screenshot → vision-model → tap loop for Coin Master Board Adventure. Hot-reloads strategy, runs periodic optimizer, and triggers recovery when stuck. | **Shut down** | `runtime/gameplay_loop.log`, `runtime/gameplay_loop.metrics.json`, `runtime/gameplay_loop.strategy.json`, `runtime/gameplay_loop_screens/` |
| **Strategy Optimizer** | `scripts/mini_optimizer.py` | One-shot text-only optimizer (`gpt-oss-120b:nitro`) that rewrites the live strategy JSON based on recent metrics and log tail. | Standalone helper | Same strategy/metrics/log files as the gameplay loop |
| **Loop Watchdog** | `scripts/loop_watchdog.py` | 5-minute watchdog that checks whether the gameplay loop is alive and whether metrics are stale; restarts the loop if needed. | **Shut down** | `runtime/loop_watchdog.log` |
| **Gameplay Option Tree** | `doc/gameplay_agent_option_tree.md` | Decision tree / artifact for user intervention when the agent encounters safety gates, blockers, or Grant milestones. | Reference doc | n/a |

### Saved snapshot

A frozen copy of the Coin Master / Grant agent is saved in:

```text
saved-agents/coin-master-grant/
```

It includes `gameplay_loop.py`, `mini_optimizer.py`, `loop_watchdog.py`,
`gameplay_loop.strategy.json`, the option tree, and a `README.md` with
resume/stop instructions.

## Core mobile-use SDK agents

Located in `minitap/mobile_use/agents/`.

| Agent | Entry point / module | Purpose |
|-------|----------------------|---------|
| **Orchestrator** | `minitap/mobile_use/agents/orchestrator/orchestrator.py` | Decides what to do next based on device state; marks subgoals complete and triggers replanning. |
| **Planner** | `minitap/mobile_use/agents/planner/planner.py` | Breaks user goals into sequential, purpose-driven subgoals. |
| **Cortex** | `minitap/mobile_use/agents/cortex/cortex.py` | Analyzes screen state and produces structured decisions for the Executor. |
| **Executor** | `minitap/mobile_use/agents/executor/executor.py` | Parses Cortex decisions and calls device tools (tap, swipe, input, etc.). |
| **Hopper** | `minitap/mobile_use/agents/hopper/hopper.py` | Extracts relevant information from batch data (e.g., app package lookups). |
| **Contextor** | `minitap/mobile_use/agents/contextor/contextor.py` | Verifies app-lock compliance; decides whether to relaunch the locked app. |
| **Outputter** | `minitap/mobile_use/agents/outputter/outputter.py` | Generates the final structured output of a multi-agent run. |
| **Summarizer** | `minitap/mobile_use/agents/summarizer/summarizer.py` | Trims message history to keep it within token limits. |
| **Video Analyzer** | `minitap/mobile_use/agents/video_analyzer/video_analyzer.py` | Analyzes video recordings of device screens on demand. |

## Other agent-related components

| Component | Location | Purpose |
|-----------|----------|---------|
| **Slot Agent** | `scripts/slot-agent.ps1`, `doc/slot-agent.md`, `minitap/mobile_use/slot_agent.py` | Standalone ADB runner for a simulated slot game; starts/stops/mirrors and presses Spin. |
| **mobile-use SDK** | `minitap/mobile_use/` | Full SDK: clients (ADB/iOS/WDA), controllers, tools, services, graph state, and examples. |
| **Skill optimization harness** | `skillopt_mobileuse/` | Training/optimization harness for mobile-use skills (`dataloader.py`, `env.py`, `rollout.py`, `verifier.py`). |
| **Setup skill** | `skills/mobile-use-setup/` | Interactive setup wizard for iOS/Android, local/platform LLM, and device config. |
| **Self-improvement skill** | `skills/mobile-use-self-improvement/` | Evidence-backed loop for improving future ADB/mobile automation runs. |

## Quick commands

```powershell
# Resume the Coin Master agent via watchdog
cd C:\dev\Desktop-Projects\mobile-agents
.venv\Scripts\python.exe saved-agents\coin-master-grant\loop_watchdog.py

# Or run the loop directly
.venv\Scripts\python.exe saved-agents\coin-master-grant\gameplay_loop.py

# Stop gracefully
New-Item -ItemType File -Path runtime\gameplay_loop.stop -Force

# Slot agent
powershell -ExecutionPolicy Bypass -File scripts\slot-agent.ps1 start -Mirror
powershell -ExecutionPolicy Bypass -File scripts\slot-agent.ps1 stop
```

## Notes

- The Coin Master gameplay agent and watchdog were shut down on 2026-06-19.
- No gameplay or watchdog processes are currently running.
- For safety rules and intervention guidance, see `AGENTS.md` and
  `doc/gameplay_agent_option_tree.md`.
