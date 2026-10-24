---
id: TASK-146
title: Implement Multi-Task Review Retry, Atomic Stage Approval, and Escalation Unblocking
type: implementation
status: done
traces_to:
- REQ-055
- SPEC-055
depends_on:
- TASK-144
- TASK-145
required_files:
- tests/test_multi_language_scenarios.py
- tests/test_multi_language_workflows.py
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/stage_runner.py
write_files:
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_scenarios.py
  tests/test_multi_language_workflows.py
---
## Objective
Update `router.py` and `stage_runner.py` to support multi-task stage review retries, atomic multi-artifact review approval, and `mt resolve` target unblocking.

## Scoped Instructions
- Include sibling `draft`/`blocked` artifacts sharing a failed-review upstream in `retry_pending` in `find_actionable_stage_target`, unblock `blocked` targets and attach resolving `DEC` IDs in `resolve_escalation`, and review all stage artifacts before calling `approve_stage_artifact` in `_step_declarative_stage`.
