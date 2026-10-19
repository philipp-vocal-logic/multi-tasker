---
id: TASK-021
title: Implement Specification Approval Support for SPEC-007
type: implementation
status: done
traces_to:
- REQ-007
- SPEC-007
depends_on:
- TASK-020
required_files:
- tests/test_orchestrator.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
verification_cmd: pytest -q
---
## Objective
Extend `approve_artifact` in `src/multi_tasker/orchestrator/lifecycle.py` to support `Specification` (`SPEC-NNN`) approval.

## Scoped Instructions
Update `approve_artifact` in `src/multi_tasker/orchestrator/lifecycle.py` to allow `SPEC` alongside `REQ` and `DEC`, validate transition and schema checks, and mark downstream `done` `Task` artifacts as `needs_update`.
