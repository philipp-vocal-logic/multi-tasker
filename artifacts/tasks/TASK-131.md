---
id: TASK-131
title: Implement Fail-Clear Ruff Execution and Remove State Transition Fallback Shim
type: implementation
status: done
traces_to:
- REQ-050
- SPEC-050
depends_on:
- TASK-130
required_files:
- tests/test_clean_code_checker.py
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/common.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/permissions_checker.py
write_files:
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/common.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/permissions_checker.py
verification_cmd: pytest -o pythonpath=src -q tests/test_clean_code_checker.py tests/test_checkers.py
  tests/test_lifecycle.py
---
## Objective
Update `format_python_files`, `_run_ruff`, and `load_state_transitions` to fail clear on `ruff` errors and remove the `fallback_policy` shim.

## Scoped Instructions
- In `src/multi_tasker/checkers/common.py`, update `format_python_files` to return `list[Finding]`, emitting `CODE_LINTER_MISSING` if `format_cmd` executable is missing and `CODE_RUFF` if `ruff format` exits non-zero.
- In `src/multi_tasker/checkers/clean_code_checker.py`, return any `format_python_files` findings from `_run_ruff` and emit `CODE_RUFF` when `ruff check` exits non-zero without parsed file-line diagnostics.
- In `src/multi_tasker/domain/parser.py` and `src/multi_tasker/checkers/permissions_checker.py`, remove `fallback_policy` from `load_state_transitions`.
