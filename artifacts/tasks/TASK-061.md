---
id: TASK-061
title: Implement BaseBranch Stage Approval Commits, Verification PYTHONPATH, and Default
  Environment
type: implementation
status: done
traces_to:
- REQ-021
- SPEC-021
depends_on:
- TASK-060
required_files:
- tests/test_stage_runner.py
- src/orchestrator/lifecycle.py
- src/orchestrator/stage_runner.py
- src/orchestrator/merge_gate.py
- src/orchestrator/prompt_builder.py
write_files:
- src/orchestrator/lifecycle.py
- src/orchestrator/stage_runner.py
- src/orchestrator/merge_gate.py
- src/orchestrator/prompt_builder.py
verification_cmd: python3 -m py_compile src/orchestrator/lifecycle.py src/orchestrator/stage_runner.py
  src/orchestrator/merge_gate.py src/orchestrator/prompt_builder.py
---
## Objective
Commit `BaseBranch` stage approval and `Escalation` status transitions, pass `Worktree` `PYTHONPATH` into `MergeGate` verification subprocesses, and resolve `default_environment` templates in `resolve_task_execution`.

## Scoped Instructions
- In `src/orchestrator/lifecycle.py`, commit changed paths in `approve_stage_artifact` and `_create_review_escalation` via `commit_traceable_change`.
- In `src/orchestrator/stage_runner.py`, commit `awaiting_human` transitions in `_dispatch_routed_escalation`.
- In `src/orchestrator/merge_gate.py`, pass `PYTHONPATH` (`worktree_path` + `multi-tasker` root) into `_run_verification_command`.
- In `src/orchestrator/prompt_builder.py`, resolve `environments.get(environment_name)` by default in `resolve_task_execution`.
