---
id: SPEC-021
title: Real-Git Pipeline Commits, Verification PYTHONPATH, and Review Traceability
  Specification
status: approved
traces_to:
- REQ-021
covers_criteria:
- REQ-021:AC-01
- REQ-021:AC-02
decisions: []
target_files:
  tests:
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/orchestrator/merge_gate.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
---
## Design Overview
Commit `BaseBranch` artifact status transitions in `approve_stage_artifact`, `_create_review_escalation`, and human-routed `Escalation` handling in `src/multi_tasker/orchestrator/lifecycle.py` and `src/multi_tasker/orchestrator/stage_runner.py` so subsequent `Worktree` creations in real Git repositories start from a clean working tree and updated `HEAD`. Propagate `Worktree` `PYTHONPATH` into `_run_verification_command` in `src/multi_tasker/orchestrator/merge_gate.py`, resolve `default_environment` templates in `resolve_task_execution` in `src/multi_tasker/orchestrator/prompt_builder.py`, and support `REV-[A-Z0-9-]+` commit identifiers in `policy/traceability.yaml` and `src/multi_tasker/checkers/code_and_git_traceability.py`.

## Public Interfaces
- `src/multi_tasker/orchestrator/lifecycle.py`:
  - `approve_stage_artifact(repository_root: Path, artifact_id: str) -> None` commits modified `BaseBranch` artifact paths via `commit_traceable_change`.
  - `_create_review_escalation(repository_root: Path, artifact_id: str, rev_path: str) -> list[Finding]` commits the new `ESC-NNN.md` and blocked target artifact.
- `src/multi_tasker/orchestrator/stage_runner.py`:
  - `_dispatch_routed_escalation(...)` commits `awaiting_human` status transitions on `BaseBranch`.
- `src/multi_tasker/orchestrator/merge_gate.py`:
  - `_run_verification_command(worktree_path: Path, command_string: str, timeout_seconds: float = 60.0) -> list[Finding]` sets `PYTHONPATH` with `worktree_path` preceding `multi-tasker`.
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `resolve_task_execution(...) -> tuple[str | None, str, str]` resolves `environments.get(environment_name)` by default.
- `src/multi_tasker/checkers/code_and_git_traceability.py`:
  - `DEFAULT_COMMIT_PATTERN` and `ARTIFACT_ID_REGEX` match `REV-[A-Z0-9-]+`.

## Test Contract Mapping
- `REQ-021:AC-01` $\rightarrow$ `tests/test_stage_runner.py::test_real_git_pipeline_commits_verification_pythonpath_and_rev_traceability`
- `REQ-021:AC-02` $\rightarrow$ `tests/test_stage_runner.py::test_real_git_pipeline_commits_verification_pythonpath_and_rev_traceability`
