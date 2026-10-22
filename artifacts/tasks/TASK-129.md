---
id: TASK-129
title: Implement Fail-Fast and Fail-Clear Linter Execution in Clean Code Checker
type: implementation
status: done
traces_to:
- REQ-049
- SPEC-049
depends_on:
- TASK-128
required_files:
- tests/test_clean_code_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
write_files:
- src/multi_tasker/checkers/clean_code_checker.py
verification_cmd: pytest -o pythonpath=src -q tests/test_clean_code_checker.py tests/test_stage_escalation.py
---
## Objective
Update `_run_ruff` and `_run_mypy` in `src/multi_tasker/checkers/clean_code_checker.py` to fail fast when enabled linter binaries are missing and fail clear on non-zero `mypy` exits.

## Scoped Instructions
- In `_run_ruff` and `_run_mypy`, when the linter is enabled and `targets` is non-empty, check `shutil.which(executable)` and return `[Finding("policy/code_quality.yaml", 1, "CODE_LINTER_MISSING", f"Linter executable '{executable}' not found in PATH.")]` if missing.
- In `_run_mypy`, set `MYPYPATH` to `f"{repository_root / 'src'}{os.pathsep}{repository_root}"` in the subprocess environment, and if `process.returncode != 0` and `findings` is empty, return a `Finding("policy/code_quality.yaml", 1, "CODE_MYPY", ...)` with the last non-empty line from `stderr` or `stdout` (or exit code message).
