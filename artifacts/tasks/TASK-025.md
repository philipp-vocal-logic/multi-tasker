---
id: TASK-025
title: Extract Worktree Task Execution Runner from Lifecycle Module for SPEC-009
type: implementation
status: done
traces_to:
- REQ-009
- SPEC-009
depends_on:
- TASK-024
required_files:
- tests/test_transitions_and_execution.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/task_runner.py
- src/multi_tasker/cli/main.py
verification_cmd: pytest -q tests/test_lifecycle.py tests/test_orchestrator.py
---
## Objective
Extract `run_scheduled_tasks` and its `Worktree` execution helpers from `src/multi_tasker/orchestrator/lifecycle.py` into `src/multi_tasker/orchestrator/task_runner.py` and update `src/multi_tasker/cli/main.py`.

## Scoped Instructions
Create `src/multi_tasker/orchestrator/task_runner.py` with `run_scheduled_tasks` and all `Worktree` invocation/finalization helpers, remove them from `src/multi_tasker/orchestrator/lifecycle.py` without re-exports, and update `src/multi_tasker/cli/main.py` imports.
