---
id: TASK-001
title: Create TestContract for REQ-001 and SPEC-001
type: test_contract
status: done
traces_to: [REQ-001, SPEC-001]
depends_on: []
required_files: []
write_files:
  - tests/test_checkers.py
  - tests/test_traceability_and_cli.py
verification_cmd: "pytest -q"
---
## Objective
Create executable `TestContract` tests in `tests/test_checkers.py` and `tests/test_traceability_and_cli.py` covering `REQ-001:AC-01` through `REQ-001:AC-05`.

## Scoped Instructions
Decorate each test function with `@traces("REQ-001", "AC-XX", "SPEC-001")` and verify both positive compliance and negative violation detection for all checkers.
