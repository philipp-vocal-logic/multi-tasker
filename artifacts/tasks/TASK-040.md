---
id: TASK-040
title: Implement Pipeline Policy Loader, Schema Validation, and Escalation Router
type: implementation
status: done
traces_to:
- REQ-014
- SPEC-014
depends_on:
- TASK-039
required_files:
- tests/test_stage_runner.py
write_files:
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/schemas_checker.py
- src/multi_tasker/orchestrator/router.py
verification_cmd: pytest -q tests/test_orchestrator.py
---
## Objective
Load and validate `policy/pipeline.yaml` in `src/multi_tasker/domain/parser.py` and `src/multi_tasker/checkers/schemas_checker.py`, and enforce policy-driven `Escalation` routing in `src/multi_tasker/orchestrator/router.py`.

## Scoped Instructions
Add `load_pipeline_policy(repository_root)` to `src/multi_tasker/domain/parser.py`. Update `check_schemas` in `src/multi_tasker/checkers/schemas_checker.py` to validate `execution_bounds`, `stages`, and `escalation_routes` in `policy/pipeline.yaml`. Update `route_escalation` in `src/multi_tasker/orchestrator/router.py` to read `escalation_routes` and `execution_bounds.max_auto_reroutes` from `load_pipeline_policy`.
