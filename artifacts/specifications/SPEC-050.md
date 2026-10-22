---
id: SPEC-050
title: Fail-Clear Ruff, Unknown Environment Guard, and Policy-Only Routing Specification
status: approved
traces_to:
- REQ-050
covers_criteria:
- REQ-050:AC-01
- REQ-050:AC-02
- REQ-050:AC-03
decisions: []
target_files:
  tests:
  - tests/test_clean_code_checker.py
  - tests/test_lifecycle.py
  - tests/test_orchestrator.py
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/checkers/common.py
  - src/multi_tasker/checkers/clean_code_checker.py
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/orchestrator/task_runner.py
---
## Design Overview
Remove remaining silent fallbacks and policy shims:
- Return `list[Finding]` from `format_python_files` in `common.py` (`CODE_LINTER_MISSING` if `format_cmd` executable is absent, `CODE_RUFF` if `ruff format` exits non-zero) and emit `CODE_RUFF` in `_run_ruff` when `ruff check` exits non-zero without parsed diagnostics.
- Emit `CLI_UNKNOWN_EXEC_ENV` on `policy/agent_execution.yaml` in `stage_runner._validate_stage_request` and `task_runner._execute_single_task` when a requested execution environment has no command template.
- Remove `fallback_policy` from `load_state_transitions` in `domain/parser.py` and remove `CATEGORY_ROUTES` from `router.py` and `prompt_builder.py`, loading `escalation_routes` via `load_artifact_schemas_and_limits` in `prompt_context.py`.

## Public Interfaces
```python
def load_state_transitions(
    repository_root: Path,
) -> dict[str, dict[str, set[str]]]: ...

def format_python_files(
    repository_root: Path,
    targets: list[str],
    ruff_configuration: dict[str, Any],
) -> list[Finding]: ...
```

## Test Contract Mapping
- `REQ-050:AC-01` -> `tests/test_clean_code_checker.py::test_output_contract_mypy_and_toggle_sensitivity`
- `REQ-050:AC-02` -> `tests/test_stage_runner.py::test_configurable_worktree_stage_execution_and_toggle`
- `REQ-050:AC-03` -> `tests/test_orchestrator.py::test_escalation_router_and_loop_prevention`
