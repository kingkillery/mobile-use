---
target: cortex
trained_on: benchmarks/mobileuse
date: 2026-05-29
baseline_score: 0.42
val_score: 0.68
test_score: 0.61
---

## Learned Mobile Skill v001

- Keep navigation concise: prefer app-launch by locked package when available.
- Prefer vertical scrolling in settings for battery/wifi/storage pages before returning.
- On failure, use home button and re-enter the requested app before retrying.
