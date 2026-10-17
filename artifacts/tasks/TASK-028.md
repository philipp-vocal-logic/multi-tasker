---
id: TASK-028
title: Implement Multi-Wave Task Runner and Diagnostic Verification Summaries
type: implementation
status: done
traces_to:
- REQ-010
- SPEC-010
depends_on:
- TASK-027
required_files:
- tests/test_lifecycle.py
write_files:
- src/orchestrator/task_runner.py
- src/orchestrator/merge_gate.py
verification_cmd: pytest -q tests/test_orchestrator.py
---
## Objective
Loop across eligible `Task` waves in `run_scheduled_tasks` and include `E   ` assertion lines in `_run_verification_command`.

## Scoped Instructions
Update `run_scheduled_tasks` in `src/orchestrator/task_runner.py` to execute successive conflict-free `Task` batches until empty or first `Finding`, and update `_run_verification_command` in `src/orchestrator/merge_gate.py` to prepend the first `E   ` line to `lines[-1]`.
