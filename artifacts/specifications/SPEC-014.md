---
id: SPEC-014
title: Declarative Logic Pipeline Policy, Escalation Routing, and Pipeline Stepper
  Specification
status: approved
traces_to:
- REQ-014
covers_criteria:
- REQ-014:AC-01
- REQ-014:AC-02
decisions: []
target_files:
  tests:
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/checkers/schemas_checker.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/cli/main.py
---
## Design Overview
Add `load_pipeline_policy(repository_root)` in `src/multi_tasker/domain/parser.py` to load `policy/pipeline.yaml`. Extend `check_schemas` in `src/multi_tasker/checkers/schemas_checker.py` to validate `execution_bounds`, `stages`, and `escalation_routes` in `policy/pipeline.yaml`. Update `route_escalation` in `src/multi_tasker/orchestrator/router.py` to read `escalation_routes` and `execution_bounds.max_auto_reroutes` from `policy/pipeline.yaml`. Add `run_declarative_pipeline` in `src/multi_tasker/orchestrator/stage_runner.py` and `--pipeline` on `mt run` in `src/multi_tasker/cli/main.py` to execute ready stages (`INT` $\rightarrow$ `REQ` $\rightarrow$ `SPEC` $\rightarrow$ `TASK`) and `routed_to_agent` `Escalation` records in isolated `Worktrees` while honoring `approval_gate` (`human`, `review-agent`, `auto`) and `max_steps_per_run`.

## Public Interfaces
- `src/multi_tasker/domain/parser.py`:
  - `load_pipeline_policy(repository_root: Path) -> dict[str, Any]`
- `src/multi_tasker/orchestrator/router.py`:
  - `route_escalation(repository_root: Path, escalation_relative_path: str, prior_reroutes: int = 0) -> RouteDecision`
- `src/multi_tasker/orchestrator/stage_runner.py`:
  - `run_declarative_pipeline(repository_root: Path, options: tuple[str | None, str | None, str | None] = (None, None, None)) -> tuple[list[str], list[Finding]]`

## Test Contract Mapping
- `REQ-014:AC-01` $\rightarrow$ `tests/test_stage_runner.py:test_pipeline_policy_validation_and_configurable_escalation_routing`: Verifies `check_schemas` validates `execution_bounds`, `stages`, and `escalation_routes` in `policy/pipeline.yaml` (emitting `PIPELINE_INVALID_STAGE` on invalid gates) and `route_escalation` enforces `escalation_routes` and `max_auto_reroutes`.
- `REQ-014:AC-02` $\rightarrow$ `tests/test_stage_runner.py:test_declarative_pipeline_execution_gates_and_auto_escalation`: Verifies `mt run --pipeline` executes stages across `human` and `auto` `approval_gate` modes and automatically dispatches and resolves a `routed_to_agent` `Escalation` before completing the rescoped `Task`.
