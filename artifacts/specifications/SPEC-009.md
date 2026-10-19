---
id: SPEC-009
title: Modular Decomposition of Orchestrator, Traceability, and Test Suites Specification
status: approved
traces_to:
- REQ-009
covers_criteria:
- REQ-009:AC-01
- REQ-009:AC-02
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  - tests/test_orchestrator.py
  - tests/test_transitions_and_execution.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/task_runner.py
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/checkers/traceability_checker.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
---
## Design Overview
Extract parallel `Worktree` `Task` execution from `src/multi_tasker/orchestrator/lifecycle.py` into `src/multi_tasker/orchestrator/task_runner.py` (`run_scheduled_tasks`) and update `src/multi_tasker/cli/main.py` to import `run_scheduled_tasks` directly from `src.orchestrator.task_runner`. Extract `TestContract` AST scanning, `Specification` `target_files` validation, and Git commit history/scope verification from `src/multi_tasker/checkers/traceability_checker.py` into `src/multi_tasker/checkers/code_and_git_traceability.py`. Rebalance `tests/test_lifecycle.py` and `tests/test_orchestrator.py` by extracting prompt synthesis, execution environment, and state transition tests into `tests/test_transitions_and_execution.py` so every repository Python file is at most 360 lines.

## Public Interfaces
- `src/multi_tasker/orchestrator/task_runner.py`:
  - `run_scheduled_tasks(repository_root: Path, max_workers: int = 1, agent_command: str | None = None, model_override: str | None = None, environment_override: str | None = None) -> tuple[list[str], list[Finding]]`
- `src/multi_tasker/orchestrator/lifecycle.py`:
  - `initialize_repository(repository_root: Path) -> list[Finding]`
  - `create_intent(repository_root: Path, text_or_file: str, timestamp: str | None = None) -> str`
  - `approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]`
  - `resolve_escalation(repository_root: Path, escalation_id: str, resolved_by: str) -> list[Finding]`
- `src/multi_tasker/checkers/code_and_git_traceability.py`:
  - `check_test_contract_coverage(repository_root: Path, by_identifier: dict[str, ArtifactDocument], rules: dict[str, Any]) -> list[Finding]`
  - `check_specification_target_files(repository_root: Path, by_identifier: dict[str, ArtifactDocument], target_paths: list[str] | None, rules: dict[str, Any]) -> list[Finding]`
  - `check_git_commit_history(repository_root: Path, by_identifier: dict[str, ArtifactDocument], rules: dict[str, Any]) -> list[Finding]`

## Test Contract Mapping
- `REQ-009:AC-01` $\rightarrow$ `tests/test_transitions_and_execution.py:test_modular_refactoring_and_file_size_ceilings`: Verifies `src.orchestrator.task_runner` exposes `run_scheduled_tasks`, `src.orchestrator.lifecycle` does not re-export `run_scheduled_tasks`, and `src.checkers.code_and_git_traceability` exposes `check_test_contract_coverage`, `check_specification_target_files`, and `check_git_commit_history`.
- `REQ-009:AC-02` $\rightarrow$ `tests/test_transitions_and_execution.py:test_modular_refactoring_and_file_size_ceilings`: Verifies every `.py` file across `src/` and `tests/` has at most 360 lines while all `TestContract` decorators remain intact.
