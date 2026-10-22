---
id: TASK-104
title: Move Review Verdict and Escalation Resolution from Lifecycle to Router
type: implementation
status: ready
traces_to:
- REQ-041
- SPEC-041
depends_on:
- TASK-103
required_files:
- artifacts/specifications/SPEC-041.md
- tests/test_stage_escalation.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/cli/main.py
verification_cmd: pytest -o pythonpath=src -q tests/test_stage_escalation.py
---
## Objective
Move `_create_review_escalation`, `evaluate_review_verdict`, and `resolve_escalation` from `lifecycle.py` into `router.py` and update callers in lockstep (`REQ-041`, `SPEC-041`).

## Scoped Instructions
In `lifecycle.py`, rename `_check_transition` and `_mark_dirty_downstream` to `check_transition` and `mark_dirty_downstream` and remove `_create_review_escalation`, `evaluate_review_verdict`, and `resolve_escalation`. Move those functions into `router.py` and update imports in `stage_runner.py` and `cli/main.py`.
