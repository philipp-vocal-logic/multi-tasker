---
id: TASK-045
title: Wire Review Gate Verdicts and Stage MergeGate Logging into Stage Runner
type: implementation
status: planned
traces_to:
  - REQ-015
  - SPEC-015
depends_on:
  - TASK-043
  - TASK-044
required_files:
  - tests/test_stage_runner.py
  - src/orchestrator/lifecycle.py
  - src/orchestrator/stage_runner.py
write_files:
  - src/orchestrator/stage_runner.py
verification_cmd: pytest -q tests/test_stage_runner.py tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Wire `evaluate_review_verdict`, `approve_stage_artifact`, and `merge_gate` event logging into `src/orchestrator/stage_runner.py`.

## Scoped Instructions
Update `run_agent_stage` in `src/orchestrator/stage_runner.py` to log `merge_gate` events to `.report/logs/tasks/<ID>.jsonl` and update `_step_declarative_stage` to call `evaluate_review_verdict` and `approve_stage_artifact`.
