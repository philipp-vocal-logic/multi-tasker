---
id: TASK-041
title: Implement Declarative Pipeline Stepper and CLI Pipeline Flag
type: implementation
status: done
traces_to:
- REQ-014
- SPEC-014
depends_on:
- TASK-039
- TASK-040
- TASK-042
required_files:
- tests/test_stage_runner.py
- src/multi_tasker/domain/parser.py
- src/multi_tasker/orchestrator/router.py
write_files:
- src/multi_tasker/checkers/schemas_checker.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/cli/main.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_stage_runner.py tests/test_orchestrator.py
---
## Objective
Implement `run_declarative_pipeline` in `src/multi_tasker/orchestrator/stage_runner.py` and wire `--pipeline` into `mt run` in `src/multi_tasker/cli/main.py`.

## Scoped Instructions
Add `run_declarative_pipeline` to `src/multi_tasker/orchestrator/stage_runner.py` to evaluate `policy/pipeline.yaml` up to `max_steps_per_run`, dispatching `routed_to_agent` `Escalation` records and actionable `stages` in isolated `Worktrees` while honoring `approval_gate` (`human`, `review-agent`, `auto`). Add `--pipeline` to `mt run` in `src/multi_tasker/cli/main.py`.
