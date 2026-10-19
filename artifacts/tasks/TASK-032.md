---
id: TASK-032
title: Integrate Worktree Task Execution and MergeGate Logging
type: implementation
status: done
traces_to:
- REQ-011
- SPEC-011
depends_on:
- TASK-030
- TASK-031
required_files:
- tests/test_interaction_logging.py
- src/multi_tasker/orchestrator/interaction_logger.py
write_files:
- src/multi_tasker/orchestrator/task_runner.py
- src/multi_tasker/orchestrator/worktree.py
verification_cmd: pytest -q
---
## Objective
Record `WorkerAgent` and `MergeGate` events and merge `Worktree` Task logs onto `BaseBranch` before `Worktree` removal.

## Scoped Instructions
Update `src/multi_tasker/orchestrator/task_runner.py` to record `agent_invocation` and `merge_gate` events and merge `Worktree` logs via `merge_worktree_task_logs` under `merge_lock`, and exclude `.report` from fallback `Worktree` copies in `src/multi_tasker/orchestrator/worktree.py`.
