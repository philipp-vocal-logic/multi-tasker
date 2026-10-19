---
id: TASK-081
title: TestContracts for Decorator Guidance and Pipeline Worker Default
type: test_contract
status: done
traces_to:
- REQ-030
- SPEC-030
depends_on: []
required_files: []
write_files:
- tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py
---
## Objective
Add `@traces("REQ-030", "AC-01", "SPEC-030")` and `@traces("REQ-030", "AC-02", "SPEC-030")` assertions in `tests/test_interaction_logging.py` verifying `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` in prompts.

## Scoped Instructions
Update `tests/test_interaction_logging.py` to trace `REQ-030:AC-01` and `REQ-030:AC-02` and assert `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` appears in `worker-agent` and `planner-agent` prompts.
