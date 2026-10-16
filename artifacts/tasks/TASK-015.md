---
id: TASK-015
title: Create TestContract for REQ-005 and SPEC-005
type: test_contract
status: done
traces_to: [REQ-005, SPEC-005]
depends_on: []
required_files: []
write_files:
  - tests/test_lifecycle.py
verification_cmd: "pytest -q tests/test_lifecycle.py"
---
## Objective
Create executable `TestContract` tests in `tests/test_lifecycle.py` covering `REQ-005:AC-01` and `REQ-005:AC-02`.

## Scoped Instructions
Decorate the test with `@traces("REQ-005", "AC-01", "SPEC-005")` and `@traces("REQ-005", "AC-02", "SPEC-005")` and verify `agy` environment template expansion, model precedence, and `MT_AGENT_MODEL` / `MT_EXECUTION_ENVIRONMENT` environment variables.
