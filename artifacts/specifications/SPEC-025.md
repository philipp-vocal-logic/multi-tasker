---
id: SPEC-025
title: Fail-Fast Worker Task Scope Validation and Explicit Check Arguments Specification
status: approved
traces_to:
- REQ-025
covers_criteria:
- REQ-025:AC-01
decisions: []
target_files:
  tests:
  - tests/test_traceability_and_cli.py
  implementation:
  - src/multi_tasker/checkers/runner.py
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/task_runner.py
---
## Design Overview
Update `run_single_check` in `src/multi_tasker/checkers/runner.py` to pass `changed_files=target_paths` into `check_permissions`. Update `_evaluate_role_permissions` and `check_permissions` in `src/multi_tasker/checkers/permissions_checker.py` to validate `_resolve_task_write_scope` even when `files` is empty (failing fast with `PERM_TASK_ID_MISSING`) and exclude the active `artifacts/tasks/{task_id}.md` file when `changed_files` is auto-detected for `worker-agent`. Update `_assemble_prompt_sections` in `src/multi_tasker/orchestrator/prompt_builder.py` to include `--task <target_id>` for `worker-agent` and remove the `"TASK-000"` fallback in `src/multi_tasker/orchestrator/task_runner.py`.

## Public Interfaces
- `run_single_check(name: str, repository_root: Path, target_paths: list[str] | None = None, agent_role: str | None = None, task_id: str | None = None) -> list[Finding]`
- `check_permissions(repository_root: Path, agent_role: str | None = None, task_id: str | None = None, changed_files: list[str] | None = None, existing_states: dict[str, str] | None = None) -> list[Finding]`

## Test Contract Mapping
- `REQ-025:AC-01` -> `tests/test_traceability_and_cli.py::test_fail_fast_worker_task_scope_and_explicit_check_paths`
