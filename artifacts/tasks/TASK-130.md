---
id: TASK-130
title: Add TestContracts for Ruff Failure, Unknown Execution Env, and Policy-Only
  Routing
type: test_contract
status: done
traces_to:
- REQ-050
- SPEC-050
depends_on: []
required_files:
- tests/test_clean_code_checker.py
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_stage_runner.py
write_files:
- tests/test_clean_code_checker.py
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_stage_runner.py
verification_cmd: python3 -m py_compile tests/test_clean_code_checker.py tests/test_lifecycle.py
  tests/test_orchestrator.py tests/test_stage_runner.py
---
## Objective
Extend `TestContracts` in `tests/test_clean_code_checker.py`, `tests/test_lifecycle.py`, `tests/test_orchestrator.py`, and `tests/test_stage_runner.py` for `REQ-050` (`AC-01`, `AC-02`, `AC-03`).

## Scoped Instructions
- In `tests/test_clean_code_checker.py`, tag `test_output_contract_mypy_and_toggle_sensitivity` with `@traces("REQ-050", "AC-01", "SPEC-050")` and assert that a failing `ruff` command without standard file-line output emits `CODE_RUFF`.
- In `tests/test_stage_runner.py`, tag `test_configurable_worktree_stage_execution_and_toggle` with `@traces("REQ-050", "AC-02", "SPEC-050")` and assert that passing an unknown `--environment` to `mt run --agent` or `mt run` emits `CLI_UNKNOWN_EXEC_ENV`.
- In `tests/test_lifecycle.py` and `tests/test_orchestrator.py`, seed `escalation_routes` in `policy/artifact_lifecycle.yaml`, tag `test_escalation_router_and_loop_prevention` with `@traces("REQ-050", "AC-03", "SPEC-050")`, and verify `CATEGORY_ROUTES` is absent from `router`.
