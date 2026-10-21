---
id: TASK-088
title: Implement Compact Templates, Layer Imports, and Role-Tailored Prompts in Prompt
  Builder
type: implementation
status: done
traces_to:
- REQ-033
- SPEC-033
depends_on:
- TASK-087
required_files:
- tests/test_interaction_logging.py
- tests/test_checkers.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py tests/test_checkers.py
  tests/test_orchestrator.py
---
## Objective
Update `src/multi_tasker/orchestrator/prompt_builder.py` to synthesize compact frontmatter-and-section templates, 3-line `ESC` contracts, layer `allowed_internal_imports`, role-tailored `Execution Steps` Step 1 and constraints, and `SPEC` `target_files` context injection while keeping `prompt_builder.py` under `400` lines.

## Scoped Instructions
Replace raw `yaml.safe_dump(schema_def)` and full `ESC` schema dumps in `src/multi_tasker/orchestrator/prompt_builder.py` with compact Markdown frontmatter + `## Heading` skeletons and a 3-line `ESC` summary. Include `allowed_internal_imports` in `_render_architecture_layers`, filter `@traces` and status hints to relevant roles, add semantic review rubric for `review-agent`, and inline `SPEC` `target_files` in `_render_target_context_section`.
