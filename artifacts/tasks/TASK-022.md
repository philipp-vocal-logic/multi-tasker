---
id: TASK-022
title: Create TestContract for REQ-008 and SPEC-008
type: test_contract
status: done
traces_to:
- REQ-008
- SPEC-008
depends_on: []
required_files: []
write_files:
- tests/test_orchestrator.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Create executable `TestContract` tests in `tests/test_orchestrator.py` covering `REQ-008:AC-01` and `REQ-008:AC-02`.

## Scoped Instructions
Add `test_atomic_approve_and_failed_run_preserve_clean_base` decorated with `@traces("REQ-008", "AC-01", "SPEC-008")` and `@traces("REQ-008", "AC-02", "SPEC-008")` in `tests/test_orchestrator.py`.
