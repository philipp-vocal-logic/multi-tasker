---
id: TASK-124
title: Update Lifecycle, Stage, and Pipeline TestContracts for Separated Policy Files
type: test_contract
status: done
traces_to:
- REQ-048
- SPEC-048
depends_on: []
required_files:
- tests/test_interaction_logging.py
- tests/test_lifecycle.py
- tests/test_pipeline_combinations.py
- tests/test_review_gates.py
- tests/test_stage_runner.py
- tests/test_task_runner.py
write_files:
- tests/test_interaction_logging.py
- tests/test_lifecycle.py
- tests/test_pipeline_combinations.py
- tests/test_review_gates.py
- tests/test_stage_runner.py
- tests/test_task_runner.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py tests/test_lifecycle.py
  tests/test_pipeline_combinations.py tests/test_review_gates.py tests/test_stage_runner.py
  tests/test_task_runner.py
---
## Objective
Update lifecycle, interaction logging, stage runner, task runner, review gate, and pipeline `TestContract` modules for the 10 separated `policy/*.yaml` files.

## Scoped Instructions
Update `tests/test_interaction_logging.py`, `tests/test_lifecycle.py`, `tests/test_pipeline_combinations.py`, `tests/test_review_gates.py`, `tests/test_stage_runner.py`, and `tests/test_task_runner.py` to seed and read `agent_permissions.yaml`, `agent_execution.yaml`, `artifact_schemas.yaml`, `artifact_limits.yaml`, `artifact_lifecycle.yaml`, `code_architecture.yaml`, `code_limits.yaml`, and `code_quality.yaml`. Tag `test_per_agent_model_precedence_and_policy_validation` with `@traces("REQ-048", "AC-01", "SPEC-048")`.
