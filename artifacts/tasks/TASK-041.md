---
id: TASK-041
title: Implement Declarative Pipeline Stepper and CLI Pipeline Flag
type: implementation
status: planned
traces_to:
  - REQ-014
  - SPEC-014
depends_on:
  - TASK-039
  - TASK-040
  - TASK-042
required_files:
  - tests/test_stage_runner.py
  - src/domain/parser.py
  - src/orchestrator/router.py
write_files:
  - src/orchestrator/stage_runner.py
  - src/cli/main.py
verification_cmd: pytest -q tests/test_stage_runner.py tests/test_orchestrator.py
---
## Objective
Implement `run_declarative_pipeline` in `src/orchestrator/stage_runner.py` and wire `--pipeline` into `mt run` in `src/cli/main.py`.

## Scoped Instructions
Add `run_declarative_pipeline` to `src/orchestrator/stage_runner.py` to evaluate `policy/pipeline.yaml` up to `max_steps_per_run`, dispatching `routed_to_agent` `Escalation` records and actionable `stages` in isolated `Worktrees` while honoring `approval_gate` (`human`, `review-agent`, `auto`). Add `--pipeline` to `mt run` in `src/cli/main.py`.
