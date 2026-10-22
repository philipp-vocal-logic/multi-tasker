---
id: SPEC-049
title: Fail-Fast and Fail-Clear Linter Execution Specification
status: approved
traces_to:
- REQ-049
covers_criteria:
- REQ-049:AC-01
- REQ-049:AC-02
- REQ-049:AC-03
decisions: []
target_files:
  tests:
  - tests/test_clean_code_checker.py
  - tests/test_stage_escalation.py
  implementation:
  - src/multi_tasker/checkers/clean_code_checker.py
---
## Design Overview
Remove silent `shutil.which` fallback skips from `_run_ruff` and `_run_mypy` in `src/multi_tasker/checkers/clean_code_checker.py`:
- When `ruff` or `mypy` is enabled in `policy/code_quality.yaml` and `targets` is non-empty, verify `shutil.which(executable)` and immediately return `[Finding("policy/code_quality.yaml", 1, "CODE_LINTER_MISSING", ...)]` if the binary is not on `PATH`.
- In `_run_mypy`, set `MYPYPATH` to `<repository_root>/src:<repository_root>` so target-scoped `MergeGate` checks resolve `multi_tasker` and `tests` imports, and if `process.returncode != 0` with no parsed `file:line:` diagnostics, emit `Finding("policy/code_quality.yaml", 1, "CODE_MYPY", ...)`.
- Update `tests/test_stage_escalation.py` to use `monkeypatch.setattr` and exact `run_scheduled_tasks` parameter names so `mypy --strict` passes.

## Public Interfaces
```python
def _run_ruff(
    repository_root: Path, targets: list[str], ruff_configuration: dict[str, Any]
) -> list[Finding]: ...

def _run_mypy(
    repository_root: Path, targets: list[str], mypy_configuration: dict[str, Any]
) -> list[Finding]: ...
```

## Test Contract Mapping
- `REQ-049:AC-01` -> `tests/test_clean_code_checker.py::test_output_contract_mypy_and_toggle_sensitivity`
- `REQ-049:AC-02` -> `tests/test_clean_code_checker.py::test_output_contract_mypy_and_toggle_sensitivity`
- `REQ-049:AC-03` -> `tests/test_stage_escalation.py::test_declarative_pipeline_max_workers_forwarding_and_failure_halt`
