---
id: SPEC-011
title: Task-Scoped Mergeable Interaction and CLI Invocation Logging Specification
status: approved
traces_to:
- REQ-011
covers_criteria:
- REQ-011:AC-01
- REQ-011:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/interaction_logger.py
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/orchestrator/task_runner.py
  - src/multi_tasker/orchestrator/worktree.py
---
## Design Overview
Create `src/multi_tasker/orchestrator/interaction_logger.py` to append structured JSONL records to `.report/logs/events.jsonl` and `.report/logs/tasks/<TASK-ID>.jsonl` while writing `.report/.gitignore` (`*\n`) so logs never dirty `BaseBranch` or `Worktree` status. Update `main` in `src/multi_tasker/cli/main.py` to measure command duration and call `record_cli_invocation` for every `mt` invocation without altering `Specification` documentation generation. Update `src/multi_tasker/orchestrator/task_runner.py` and `src/multi_tasker/orchestrator/worktree.py` to log `WorkerAgent` subprocess and `MergeGate` events inside the `Worktree` and merge `Worktree` Task logs onto `BaseBranch` under `merge_lock` before `remove_worktree`.

## Public Interfaces
- `src/multi_tasker/orchestrator/interaction_logger.py`:
  - `record_cli_invocation(repository_root: Path, command: str, arguments: list[str], exit_code: int, duration_ms: int) -> Path`
  - `record_task_event(repository_root: Path, task_id: str, event_type: str, details: dict[str, Any], execution_context: tuple[str | None, str, str] | None = None) -> Path`
  - `merge_worktree_task_logs(repository_root: Path, worktree_path: Path, task_id: str) -> None`
  - `read_task_log(repository_root: Path, task_id: str) -> list[dict[str, Any]]`
  - `read_event_log(repository_root: Path) -> list[dict[str, Any]]`
- `src/multi_tasker/cli/main.py`:
  - `main(argument_values: list[str] | None = None) -> int`

## Test Contract Mapping
- `REQ-011:AC-01` $\rightarrow$ `tests/test_interaction_logging.py:test_cli_invocations_logged_to_events_and_task_logs`: Verifies `mt` CLI commands append structured JSONL entries to `.report/logs/events.jsonl` and `.report/logs/tasks/<TASK-ID>.jsonl` while keeping `.report/` gitignored and preserving zero-noise stdout.
- `REQ-011:AC-02` $\rightarrow$ `tests/test_interaction_logging.py:test_worktree_task_execution_and_merge_gate_logs_merged`: Verifies `mt run` records `WorkerAgent` subprocess invocations, in-Worktree `mt` CLI calls, and `MergeGate` outcomes, and merges them into `.report/logs/tasks/<TASK-ID>.jsonl` and `.report/logs/events.jsonl` on both pass and failure.
