## Mobile-use benchmark and optimization scaffolding

This folder contains deterministic benchmark tasks for the SkillOpt loop.

### Quick offline start (no phone required)

Run this first to validate item files and command wiring:

```powershell
uv run python benchmarks/mobileuse/run_benchmark.py --split train --validate-only
```

If you want output in a dedicated path:

```powershell
uv run python benchmarks/mobileuse/run_benchmark.py --split val --validate-only --results-output outputs/mobileuse_run/val_validate.json
```

This checks:
- item schema (`id`, `platform`, `goal`, `locked_app_package`, commands)
- command tokens (reset/verifier command executables)

### Running on-device (next step)

```powershell
uv run python benchmarks/mobileuse/run_benchmark.py --split train --results-output outputs/mobileuse_run/train_results.json
```

Set a skill path and target (recommended default):

```powershell
$env:MOBILE_USE_SKILL_PATH="C:\Dev\Desktop-Projects\mobile-agents\optimized-skills\best_skill.md"
$env:MOBILE_USE_SKILL_TARGETS="cortex"
uv run python benchmarks/mobileuse/run_benchmark.py --split train --skill-path $env:MOBILE_USE_SKILL_PATH
```

### SkillOpt integration

Configured in `skillopt_mobileuse/configs/mobileuse/default.yaml` with:
- `workers: 1`
- `batch_size: 3`
- `num_epochs: 2`

Run the optimizer:

```powershell
uv run python benchmarks/mobileuse/run_optimization.py --config skillopt_mobileuse/configs/mobileuse/default.yaml --dry-run
uv run python benchmarks/mobileuse/run_optimization.py --config skillopt_mobileuse/configs/mobileuse/default.yaml --output-dir outputs/mobileuse_opt
```

Promotion to `optimized-skills/best_skill.md` is manual:

```powershell
uv run python benchmarks/mobileuse/promote_skill.py optimized-skills/mobileuse-cortex-v002.md
```

To include scoring metadata in the promoted file:

```powershell
uv run python benchmarks/mobileuse/promote_skill.py optimized-skills/mobileuse-cortex-v002.md --baseline-score 0.42 --val-score 0.68 --test-score 0.61
```
