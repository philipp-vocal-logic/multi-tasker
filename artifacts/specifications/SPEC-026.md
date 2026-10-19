---
id: SPEC-026
title: Standard src/multi_tasker Package Layout and Subprocess PYTHONPATH Isolation
  Specification
status: approved
traces_to:
- REQ-026
covers_criteria:
- REQ-026:AC-01
- REQ-026:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  - tests/test_transitions_and_execution.py
  implementation:
  - src/multi_tasker/checkers/code_and_git_traceability.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/merge_gate.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Move `src/{domain,checkers,orchestrator,cli}` into `src/multi_tasker/{domain,checkers,orchestrator,cli}` with `src/multi_tasker/__init__.py` and rewrite internal imports to `multi_tasker.*`. Update `pyproject.toml` so `package-dir` maps `"multi_tasker" = "src/multi_tasker"` and `"multi_tasker.policy_templates" = "policy"` without top-level `src`. Update `policy/architecture.yaml` to use `src/multi_tasker/**` paths and `multi_tasker.*` allowed/forbidden imports. Update `lifecycle.py` template resolution to `parents[3] / "policy"`, and isolate `PYTHONPATH` in `merge_gate.py`, `prompt_builder.py`, and `stage_runner.py` to `worktree_path` (plus existing `os.environ.get("PYTHONPATH")` if set) without appending the `multi-tasker` root.

## Public Interfaces
- `pyproject.toml`: `mt = "multi_tasker.cli.main:main"`, `package-dir = {"multi_tasker" = "src/multi_tasker", "multi_tasker.policy_templates" = "policy"}`
- `src/multi_tasker/orchestrator/merge_gate.py`: `_run_verification_command` sets `PYTHONPATH` to `str(worktree_path)`
- `src/multi_tasker/orchestrator/prompt_builder.py`: `prepare_worker_invocation` sets `PYTHONPATH` to `str(worktree_path)`
- `src/multi_tasker/orchestrator/stage_runner.py`: `_prepare_stage_invocation` sets `PYTHONPATH` to `str(worktree_path)`

## Test Contract Mapping
- `REQ-026:AC-01` -> `tests/test_transitions_and_execution.py::test_modular_refactoring_and_file_size_ceilings`
- `REQ-026:AC-02` -> `tests/test_interaction_logging.py::test_architecture_custom_package_and_worktree_pythonpath`
