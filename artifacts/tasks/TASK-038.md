---
id: TASK-038
title: Implement Configurable Worktree Stage Runner and CLI Agent Dispatch
type: implementation
status: done
traces_to:
- REQ-013
- SPEC-013
depends_on:
- TASK-036
- TASK-037
required_files:
- tests/test_stage_runner.py
- src/multi_tasker/orchestrator/prompt_builder.py
write_files:
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/cli/main.py
verification_cmd: pytest -q
---
## Objective
Create `src/multi_tasker/orchestrator/stage_runner.py` and wire `--agent` and `--target` into `mt run` in `src/multi_tasker/cli/main.py`.

## Scoped Instructions
Implement `is_worktree_agent_enabled` and `run_agent_stage` in `src/multi_tasker/orchestrator/stage_runner.py` to run enabled agent roles in isolated `Worktrees` verified by `MergeGate`, and update `src/multi_tasker/cli/main.py` (`mt run`) to support `--agent` and `--target` and enforce `worktree_execution`.
