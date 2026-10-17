---
id: TASK-020
title: Create TestContract for REQ-007 and SPEC-007
type: test_contract
status: planned
traces_to:
  - REQ-007
  - SPEC-007
depends_on: []
required_files: []
write_files:
  - tests/test_orchestrator.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Create executable `TestContract` tests in `tests/test_orchestrator.py` covering `REQ-007:AC-01` and `REQ-007:AC-02`.

## Scoped Instructions
Add `test_approve_specification_and_dirty_task_propagation` decorated with `@traces("REQ-007", "AC-01", "SPEC-007")` and `test_exhaustive_agent_and_lifecycle_state_transitions` decorated with `@traces("REQ-007", "AC-02", "SPEC-007")` in `tests/test_orchestrator.py`.
