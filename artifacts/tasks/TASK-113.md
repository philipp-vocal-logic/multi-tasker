---
id: TASK-113
title: Split Lifecycle and TaskRunner TestContracts and Remove Compound Filename
type: test_contract
status: done
traces_to:
- REQ-045
- SPEC-045
depends_on:
- TASK-112
required_files:
- tests/test_lifecycle.py
- tests/test_transitions_and_execution.py
write_files:
- tests/test_transitions_and_execution.py
- tests/test_lifecycle.py
- tests/test_task_runner.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py tests/test_task_runner.py
---
## Objective
Replace `tests/test_transitions_and_execution.py` with `tests/test_task_runner.py` and trim `tests/test_lifecycle.py` so every module stays below `400` lines.

## Scoped Instructions
Delete `tests/test_transitions_and_execution.py`, move state-transition approval tests into `tests/test_lifecycle.py` and `Task` execution tests into `tests/test_task_runner.py`, and decorate `test_modular_refactoring_and_file_size_ceilings` with `@traces("REQ-045", "AC-03", "SPEC-045")` asserting zero `*_and_*.py` files in `tests/` and `collect_refactoring_targets(root) == []`.
