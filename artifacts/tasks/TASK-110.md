---
id: TASK-110
title: Update External Agents Guide with Canonical Prompt Command
type: implementation
status: done
traces_to:
- REQ-044
- SPEC-044
depends_on:
- TASK-109
required_files:
- artifacts/specifications/SPEC-044.md
- tests/test_stage_escalation.py
write_files:
- src/multi_tasker/orchestrator/documentation_generator.py
verification_cmd: pytest -o pythonpath=src -q tests/test_stage_escalation.py
---
## Objective
Update `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to document `mt prompt <agent-role> [--target <id>]` (`REQ-044`, `SPEC-044`).

## Scoped Instructions
Update step 5 of `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to include `mt prompt <agent-role> [--target <id>]`.
