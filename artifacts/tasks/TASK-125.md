---
id: TASK-125
title: Update Domain Parser, Checkers, and CLI Output for Separated Policy Files
type: implementation
status: ready
traces_to:
- REQ-048
- SPEC-048
depends_on:
- TASK-123
- TASK-124
required_files:
- tests/test_architecture_checker.py
- tests/test_checkers.py
- tests/test_clean_code_checker.py
- tests/test_schemas_checker.py
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/permissions_checker.py
- src/multi_tasker/checkers/schemas_checker.py
write_files:
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/permissions_checker.py
- src/multi_tasker/checkers/schemas_checker.py
- src/multi_tasker/cli/output.py
verification_cmd: pytest -o pythonpath=src -q tests/test_architecture_checker.py tests/test_checkers.py
  tests/test_clean_code_checker.py tests/test_traceability_checker.py
---
## Objective
Update `domain/parser.py`, all policy checkers, and `cli/output.py` to load and enforce the concern-separated `policy/*.yaml` files.

## Scoped Instructions
Update `domain/parser.py` to load `state_transitions`, `execution_bounds`, `stages`, and `escalation_routes` from `policy/artifact_lifecycle.yaml`. Update `architecture_checker.py` (`code_architecture.yaml`), `clean_code_checker.py` and `cli/output.py` (`code_quality.yaml`), `limits_checker.py` (`code_limits.yaml`), `permissions_checker.py` (`agent_permissions.yaml` and `agent_execution.yaml`), and `schemas_checker.py` (`artifact_schemas.yaml` and `artifact_limits.yaml`).
