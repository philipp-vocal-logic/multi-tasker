---
id: TASK-096
title: Implement Multi-REQ Intent Completion Guard and Multi-Artifact Stage Review
type: implementation
status: done
traces_to:
- REQ-037
- SPEC-037
depends_on:
- TASK-095
required_files:
- artifacts/requirements/REQ-037.md
- artifacts/specifications/SPEC-037.md
- tests/test_lifecycle.py
- tests/test_stage_runner.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/stage_runner.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_lifecycle.py tests/test_stage_runner.py
  -k "multi_requirement or multi_artifact"
---
## Objective
Update `lifecycle.py` so `INT` transitions to `processed` only when all linked `REQ`s are `approved` (keeping `INT` in `processing` while any sibling `REQ` is unapproved), and update `stage_runner.py` so `_step_declarative_stage` reviews all produced stage artifacts.

## Scoped Instructions
- In `lifecycle.py`, extract `_sync_upstream_intents` and keep total lines below `refactor_target_file_lines: 400`.
- In `stage_runner.py`, remove `and index == 0` in `_step_declarative_stage` so `review-agent` verifies every produced artifact before approving.
