---
id: TASK-077
title: TestContracts for Canonical Self-Contained Role Prompts
type: test_contract
status: ready
traces_to:
- REQ-028
- SPEC-028
depends_on: []
required_files: []
write_files:
- tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py
---
## Objective
Update `tests/test_interaction_logging.py` with `@traces("REQ-028", ...)` TestContracts verifying single self-contained prompt synthesis (`Execution Steps`, `Architecture Layers`, `mt check all --agent`) and removal of `context_mode` branching.

## Scoped Instructions
Update `tests/test_interaction_logging.py` to test self-contained prompt synthesis and `execution_environments` validation without `context_mode`.
