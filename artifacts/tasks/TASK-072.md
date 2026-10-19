---
id: TASK-072
title: Add TestContracts for src/multi_tasker Package Layout and Subprocess PYTHONPATH
  Isolation
type: test_contract
status: done
traces_to:
- REQ-026
- SPEC-026
depends_on: []
required_files:
- tests/test_interaction_logging.py
- tests/test_transitions_and_execution.py
write_files:
- tests/test_interaction_logging.py
- tests/test_transitions_and_execution.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py tests/test_transitions_and_execution.py
---
## Objective
Update `tests/test_interaction_logging.py` and `tests/test_transitions_and_execution.py` with `@traces("REQ-026", ...)` assertions verifying the `src/multi_tasker/**` package layout and isolated `Worktree` / `MergeGate` subprocess `PYTHONPATH`.

## Scoped Instructions
Tag `test_modular_refactoring_and_file_size_ceilings` with `@traces("REQ-026", "AC-01", "SPEC-026")` and assert `multi_tasker.*` module imports and absence of `"src"` in `pyproject.toml` `package-dir`. Tag `test_architecture_custom_package_and_worktree_pythonpath` with `@traces("REQ-026", "AC-02", "SPEC-026")` and assert `PYTHONPATH` equals `str(tmp_path)` without the `multi-tasker` repository root.
