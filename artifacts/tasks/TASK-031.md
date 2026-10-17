---
id: TASK-031
title: Implement Interaction Logger and CLI Invocation Logging
type: implementation
status: done
traces_to:
- REQ-011
- SPEC-011
depends_on:
- TASK-030
required_files:
- tests/test_interaction_logging.py
write_files:
- src/orchestrator/interaction_logger.py
- src/cli/main.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Create `src/orchestrator/interaction_logger.py` and log every `mt` CLI command execution in `src/cli/main.py`.

## Scoped Instructions
Implement `record_cli_invocation`, `record_task_event`, `merge_worktree_task_logs`, `read_task_log`, and `read_event_log` in `src/orchestrator/interaction_logger.py`, and update `main` in `src/cli/main.py` to log every CLI command invocation with duration and exit code into `.report/logs/`.
