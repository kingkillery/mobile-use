# Agent Guidance

## Index

For a complete list of agents and components, see
`doc/mobile_agents_index.md`.

## Gameplay Loop

When working with the live Coin Master / Grant gameplay loop:

- The main loop is `scripts/gameplay_loop.py`.
- The watchdog is `scripts/loop_watchdog.py`.
- A saved snapshot is in `saved-agents/coin-master-grant/`.
- Runtime state lives in `runtime/gameplay_loop.*`.

### If a question or blocker arises

Use the option tree in `doc/gameplay_agent_option_tree.md`. Present the
relevant options to the user and wait for their choice before continuing.

### Safety rules

- Never complete purchases, payments, identity verification, or account linking.
- Allowed actions: spin/roll, build, claim free rewards, OK, close, skip, later,
  and tutorial-guided attack/raid.
- If an unsafe screen appears, prefer dismissing it safely or stopping and
  reporting.
