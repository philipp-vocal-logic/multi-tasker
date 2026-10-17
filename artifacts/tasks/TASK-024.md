---
id: TASK-024
title: Rebalance Test Suites and Create TestContract for REQ-009 and SPEC-009
type: test_contract
status: done
traces_to:
- REQ-009
- SPEC-009
depends_on: []
required_files: []
write_files:
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_transitions_and_execution.py
verification_cmd: pytest -q tests/test_lifecycle.py tests/test_orchestrator.py
---
## Objective
Extract prompt, execution, and state transition tests from `tests/test_lifecycle.py` and `tests/test_orchestrator.py` into `tests/test_transitions_and_execution.py` and add `@traces("REQ-009", ...)` tests.

## Scoped Instructions
Move `SPEC-004` through `SPEC-008` prompt, execution, report, and state transition tests into `tests/test_transitions_and_execution.py` and add `test_modular_refactoring_and_file_size_ceilings` decorated with `@traces("REQ-009", "AC-01", "SPEC-009")` and `@traces("REQ-009", "AC-02", "SPEC-009")`.
