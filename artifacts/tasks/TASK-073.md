---
id: TASK-073
title: Implement src/multi_tasker Package Layout and Subprocess PYTHONPATH Isolation
type: implementation
status: done
traces_to:
- REQ-026
- SPEC-026
depends_on:
- TASK-072
required_files:
- tests/test_interaction_logging.py
- tests/test_transitions_and_execution.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -q tests/test_interaction_logging.py tests/test_transitions_and_execution.py
---
## Objective
Isolate `Worktree` and `MergeGate` subprocess `PYTHONPATH` to `worktree_path` only and update `lifecycle.py` template resolution for the `src/multi_tasker/**` package hierarchy.

## Scoped Instructions
Update `_scaffold_default_policies_and_gitignore` in `src/multi_tasker/orchestrator/lifecycle.py` to resolve `policy/` from `Path(__file__).resolve().parents[3] / "policy"`. Update `_run_verification_command` in `merge_gate.py`, `prepare_worker_invocation` in `prompt_builder.py`, and `_prepare_stage_invocation` in `stage_runner.py` to set `PYTHONPATH` to `str(worktree_path)` without appending the `multi-tasker` repository root.
