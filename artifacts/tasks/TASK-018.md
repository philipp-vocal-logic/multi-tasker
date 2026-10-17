---
id: TASK-018
title: Create TestContract for REQ-006 and SPEC-006
type: test_contract
status: done
traces_to:
- REQ-006
- SPEC-006
depends_on: []
required_files: []
write_files:
- tests/test_orchestrator.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Create executable `TestContract` tests in `tests/test_orchestrator.py` covering `REQ-006:AC-01` and `REQ-006:AC-02`.

## Scoped Instructions
Decorate `test_continual_report_documentation_generation` with `@traces("REQ-006", "AC-01", "SPEC-006")` and `@traces("REQ-006", "AC-02", "SPEC-006")` and verify `.report/specification.md` and `.report/.gitignore` generation across `mt initialize`, `mt intent`, `mt approve`, and `mt documentation`.
