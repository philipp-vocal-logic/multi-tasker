---
id: TASK-127
title: Update Documentation Generator for Separated Policy Files
type: implementation
status: done
traces_to:
- REQ-048
- SPEC-048
depends_on:
- TASK-123
- TASK-124
- TASK-126
required_files:
- tests/test_documentation_generator.py
- tests/test_interaction_logging.py
- src/multi_tasker/orchestrator/documentation_generator.py
write_files:
- src/multi_tasker/orchestrator/documentation_generator.py
verification_cmd: pytest -o pythonpath=src -q tests/test_documentation_generator.py
  tests/test_interaction_logging.py
---
## Objective
Update `src/multi_tasker/orchestrator/documentation_generator.py` to read from `code_architecture.yaml`, `agent_permissions.yaml`, `code_limits.yaml`, and `artifact_lifecycle.yaml` and emit the new policy filenames in `AGENTS.md`.

## Scoped Instructions
Update `_render_architecture_section`, `_render_permissions_section`, `_render_state_lifecycles_section`, `_render_limits_and_glossary_section`, `_render_pipeline_section`, `_render_example_prompts_section`, and `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to reference the concern-separated `policy/*.yaml` files.
