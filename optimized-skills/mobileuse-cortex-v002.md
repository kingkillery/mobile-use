---
target: cortex
trained_on: benchmarks/mobileuse
date: 2026-05-29
baseline_score: 0.42
val_score: 0.68
test_score: 0.61
---

## Learned Mobile Skill v002

- Open target app from home screen using recent app tiles when package lock is unavailable.
- In Settings, open system sections in this priority: battery -> wifi -> storage.
- If hierarchy is stale, issue one short wait then retry the same action once before changing plan.
