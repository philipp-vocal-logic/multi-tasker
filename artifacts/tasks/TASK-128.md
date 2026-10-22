---
id: TASK-128
title: Add Fail-Fast Linter TestContracts and Fix Stage Escalation Mypy Types
type: test_contract
status: done
traces_to:
- REQ-049
- SPEC-049
depends_on: []
required_files:
- tests/test_clean_code_checker.py
- tests/test_stage_escalation.py
- src/multi_tasker/orchestrator/task_runner.py
write_files:
- tests/test_clean_code_checker.py
- tests/test_stage_escalation.py
verification_cmd: pytest -o pythonpath=src -q tests/test_stage_escalation.py
---
## Objective
Update `tests/test_clean_code_checker.py` and `tests/test_stage_escalation.py` to verify fail-fast/fail-clear linter execution and satisfy `mypy --strict`.

## Scoped Instructions
- In `tests/test_clean_code_checker.py`, tag `test_output_contract_mypy_and_toggle_sensitivity` with `@traces("REQ-049", "AC-01", "SPEC-049")` and `@traces("REQ-049", "AC-02", "SPEC-049")` and assert that missing enabled `ruff`/`mypy` binaries emit `CODE_LINTER_MISSING` and non-zero `mypy` exits without file-line output emit `CODE_MYPY`.
- In `tests/test_stage_escalation.py`, tag `test_declarative_pipeline_max_workers_forwarding_and_failure_halt` with `@traces("REQ-049", "AC-03", "SPEC-049")`, import `pytest`, accept `monkeypatch: pytest.MonkeyPatch`, use `monkeypatch.setattr(stage_runner, "run_scheduled_tasks", fake_scheduled)`, and match `run_scheduled_tasks` parameter names.
