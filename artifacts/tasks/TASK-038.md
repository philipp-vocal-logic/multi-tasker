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
- src/orchestrator/prompt_builder.py
write_files:
- src/orchestrator/stage_runner.py
- src/cli/main.py
verification_cmd: pytest -q
---
## Objective
Create `src/orchestrator/stage_runner.py` and wire `--agent` and `--target` into `mt run` in `src/cli/main.py`.

## Scoped Instructions
Implement `is_worktree_agent_enabled` and `run_agent_stage` in `src/orchestrator/stage_runner.py` to run enabled agent roles in isolated `Worktrees` verified by `MergeGate`, and update `src/cli/main.py` (`mt run`) to support `--agent` and `--target` and enforce `worktree_execution`.
