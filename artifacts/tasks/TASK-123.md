---
id: TASK-123
title: Update Checker and Orchestrator TestContracts for Separated Policy Files
type: test_contract
status: done
traces_to:
- REQ-048
- SPEC-048
depends_on: []
required_files:
- tests/test_architecture_checker.py
- tests/test_checkers.py
- tests/test_clean_code_checker.py
- tests/test_schemas_checker.py
- tests/test_traceability_checker.py
- tests/test_orchestrator.py
write_files:
- tests/test_architecture_checker.py
- tests/test_checkers.py
- tests/test_clean_code_checker.py
- tests/test_schemas_checker.py
- tests/test_traceability_checker.py
- tests/test_orchestrator.py
verification_cmd: python3 -m py_compile tests/test_architecture_checker.py tests/test_checkers.py
  tests/test_clean_code_checker.py tests/test_schemas_checker.py tests/test_traceability_checker.py
  tests/test_orchestrator.py
---
## Objective
Update checker and `Orchestrator` `TestContract` modules to seed and assert the 10 single-concern `policy/*.yaml` files and add `@traces("REQ-048", ...)` decorators.

## Scoped Instructions
Update `tests/test_architecture_checker.py`, `tests/test_checkers.py`, `tests/test_clean_code_checker.py`, `tests/test_schemas_checker.py`, `tests/test_traceability_checker.py`, and `tests/test_orchestrator.py` to use `code_architecture.yaml`, `code_quality.yaml`, `code_limits.yaml`, `artifact_schemas.yaml`, `artifact_limits.yaml`, `artifact_lifecycle.yaml`, `agent_permissions.yaml`, and `agent_execution.yaml`. Tag `test_aligned_policy_limits_and_prompt_artifact_constraints` with `@traces("REQ-048", "AC-02", "SPEC-048")` and `test_all_policy_yaml_keys_are_enforced_and_read` with `@traces("REQ-048", "AC-03", "SPEC-048")`.
