---
id: TASK-111
title: Split Checker and CLI TestContracts into Single-Concern Modules
type: test_contract
status: ready
traces_to:
  - REQ-045
  - SPEC-045
depends_on: []
required_files:
  - tests/test_checkers.py
  - tests/test_traceability_and_cli.py
write_files:
  - tests/test_traceability_and_cli.py
  - tests/test_checkers.py
  - tests/test_schemas_checker.py
  - tests/test_clean_code_checker.py
  - tests/test_architecture_checker.py
  - tests/test_traceability_checker.py
  - tests/test_cli.py
verification_cmd: "python3 -m py_compile tests/test_checkers.py tests/test_schemas_checker.py tests/test_clean_code_checker.py tests/test_architecture_checker.py tests/test_traceability_checker.py tests/test_cli.py"
---
## Objective
Split checker and CLI `TestContract` suites out of `tests/test_checkers.py` and `tests/test_traceability_and_cli.py` into single-concern test modules and delete `tests/test_traceability_and_cli.py`.

## Scoped Instructions
Delete `tests/test_traceability_and_cli.py`, trim `tests/test_checkers.py`, and create `tests/test_schemas_checker.py` (including `@traces("REQ-045", "AC-01", "SPEC-045")` on `test_aligned_policy_limits_and_prompt_artifact_constraints` asserting `max_write_files == 8` and `max_required_files == 10`), `tests/test_clean_code_checker.py`, `tests/test_architecture_checker.py`, `tests/test_traceability_checker.py`, and `tests/test_cli.py`.
