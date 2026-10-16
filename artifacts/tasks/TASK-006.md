---
id: TASK-006
title: Create TestContract for REQ-002 and SPEC-002
type: test_contract
status: done
traces_to: [REQ-002, SPEC-002]
depends_on: []
required_files: []
write_files:
  - tests/test_orchestrator.py
verification_cmd: "pytest -q tests/test_orchestrator.py"
---
## Objective
Create executable `TestContract` tests in `tests/test_orchestrator.py` covering `REQ-002:AC-01` through `REQ-002:AC-04`.

## Scoped Instructions
Decorate each test function with `@traces("REQ-002", "AC-XX", "SPEC-002")` and verify Worktree isolation, MergeGate evaluation, parallel scheduling, and Escalation routing.
