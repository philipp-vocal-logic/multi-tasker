---
id: TASK-108
title: Forward Max-Workers Through Declarative Pipeline Runner
type: implementation
status: done
traces_to:
- REQ-043
- SPEC-043
depends_on:
- TASK-107
required_files:
- artifacts/specifications/SPEC-043.md
- tests/test_stage_escalation.py
write_files:
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_stage_escalation.py
---
## Objective
Forward `max_workers` from `_dispatch_run_target` in `cli/main.py` through `run_declarative_pipeline` and `_step_declarative_stage` in `stage_runner.py` (`REQ-043`, `SPEC-043`).

## Scoped Instructions
Add `max_workers: int = 1` to `run_declarative_pipeline` and `_step_declarative_stage` in `src/multi_tasker/orchestrator/stage_runner.py`, pass it to `run_scheduled_tasks`, and pass `int(getattr(arguments, "max_workers", 1))` from `_dispatch_run_target` in `src/multi_tasker/cli/main.py`.
