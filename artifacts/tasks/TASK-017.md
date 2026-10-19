---
id: TASK-017
title: "Implement CLI Model and Environment Flags and Worktree Execution for SPEC-005"
type: implementation
status: done
traces_to: [REQ-005, SPEC-005]
depends_on: [TASK-015, TASK-016]
required_files:
  - tests/test_lifecycle.py
write_files:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/cli/main.py
verification_cmd: "pytest -q"
---
## Objective
Add `--model` and `--environment` CLI flags to `mt run` and integrate template expansion and environment variable injection into worktree task execution.

## Scoped Instructions
Update `src/multi_tasker/orchestrator/lifecycle.py` and `src/multi_tasker/cli/main.py` to support `--model` and `--environment` CLI flags on `mt run`, expand `{model}`, `{task_id}`, and `{prompt_file}` placeholders, and export `MT_AGENT_MODEL` and `MT_EXECUTION_ENVIRONMENT` inside worktree execution.
