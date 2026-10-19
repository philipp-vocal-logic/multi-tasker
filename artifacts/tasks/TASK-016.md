---
id: TASK-016
title: Implement Execution Environment Validation and Model Resolution for SPEC-005
type: implementation
status: done
traces_to: [REQ-005, SPEC-005]
depends_on: [TASK-015]
required_files:
  - tests/test_lifecycle.py
write_files:
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/orchestrator/prompt_builder.py
verification_cmd: "pytest -q tests/test_orchestrator.py"
---
## Objective
Validate `execution_environments` in `src/multi_tasker/checkers/permissions_checker.py` and implement `resolve_task_execution` in `src/multi_tasker/orchestrator/prompt_builder.py`.

## Scoped Instructions
Ensure CLI > Task > Policy precedence for `model` and `execution_environment` and full policy key coverage.
