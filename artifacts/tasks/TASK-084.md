---
id: TASK-084
title: Implement Streamlined Role Prompt Synthesis in Prompt Builder
type: implementation
status: done
traces_to:
- REQ-031
- SPEC-031
depends_on:
- TASK-083
required_files:
- tests/test_interaction_logging.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py tests/test_orchestrator.py
  tests/test_checkers.py
---
## Objective
Update `src/multi_tasker/orchestrator/prompt_builder.py` to expand `$TASK_WRITE_FILES`, render concrete verification commands for `worker-agent`, omit `TASK` schema for `worker-agent`, and specify target statuses.

## Scoped Instructions
Update `ROLE_TO_OUTPUT_SCHEMA`, `_render_permissions_section`, and `_assemble_prompt_sections` in `src/multi_tasker/orchestrator/prompt_builder.py`.
