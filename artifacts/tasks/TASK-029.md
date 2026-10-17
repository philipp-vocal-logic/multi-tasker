---
id: TASK-029
title: Implement Target-Scoped Traceability Validation on Artifact Approval
type: implementation
status: done
traces_to:
- REQ-010
- SPEC-010
depends_on:
- TASK-027
- TASK-028
required_files:
- tests/test_lifecycle.py
- src/orchestrator/task_runner.py
write_files:
- src/checkers/traceability_checker.py
- src/orchestrator/lifecycle.py
verification_cmd: pytest -q
---
## Objective
Scope `check_traceability` by `target_paths` and enforce `traceability` checks in `approve_artifact` and `resolve_escalation`.

## Scoped Instructions
Update `check_traceability` in `src/checkers/traceability_checker.py` to filter document reference checks by `target_paths` and gate task/git checks by stage, and include `"traceability"` in `approve_artifact` and `resolve_escalation` in `src/orchestrator/lifecycle.py`.
