---
id: TASK-050
title: Relocate REQ-016 TestContracts to test_interaction_logging to Respect 360-Line
  Ceiling
type: test_contract
status: done
traces_to:
- REQ-016
- SPEC-016
depends_on:
- TASK-047
- TASK-048
- TASK-049
required_files:
- tests/test_lifecycle.py
- tests/test_traceability_and_cli.py
- tests/test_interaction_logging.py
write_files:
- tests/test_lifecycle.py
- tests/test_traceability_and_cli.py
- tests/test_interaction_logging.py
verification_cmd: pytest -q tests/test_interaction_logging.py tests/test_lifecycle.py
  tests/test_traceability_and_cli.py
---
## Objective
Move `REQ-016` test contracts into `tests/test_interaction_logging.py` so `tests/test_lifecycle.py` and `tests/test_traceability_and_cli.py` remain within 360 lines.

## Scoped Instructions
Relocate `test_initialize_scaffolds_default_policies_and_gitignore` from `tests/test_lifecycle.py` and `test_architecture_custom_package_and_worktree_pythonpath` from `tests/test_traceability_and_cli.py` into `tests/test_interaction_logging.py`.
