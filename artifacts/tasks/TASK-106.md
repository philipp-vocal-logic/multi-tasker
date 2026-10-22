---
id: TASK-106
title: Implement Stage-Agent Escalation Persistence and Routing
type: implementation
status: ready
traces_to:
- REQ-042
- SPEC-042
depends_on:
- TASK-105
required_files:
- artifacts/specifications/SPEC-042.md
- tests/test_stage_escalation.py
write_files:
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_stage_escalation.py
---
## Objective
Implement `finalize_stage_escalation` in `router.py` and wire it into `_finalize_stage_outcome` in `stage_runner.py` (`REQ-042`, `SPEC-042`).

## Scoped Instructions
Add `finalize_stage_escalation` in `src/multi_tasker/orchestrator/router.py` and call it from `_finalize_stage_outcome` in `src/multi_tasker/orchestrator/stage_runner.py` when `outcome.escalated and outcome.escalation_path`.
