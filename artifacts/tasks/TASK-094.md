---
id: TASK-094
title: Implement Atomic Requirement Decomposition Contract and Existing Catalog
type: implementation
status: done
traces_to:
- REQ-036
- SPEC-036
depends_on:
- TASK-093
required_files:
- artifacts/requirements/REQ-036.md
- artifacts/specifications/SPEC-036.md
- tests/test_orchestrator.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: pytest -o pythonpath=src -q tests/test_orchestrator.py -k atomic_requirement
---
## Objective
Implement `render_decomposition_contract`, `_render_existing_requirements_catalog`, and the updated `ReviewAgent` `Semantic Review Rubric` in `prompt_context.py` and `prompt_builder.py` while keeping `prompt_builder.py` below `refactor_target_file_lines`.

## Scoped Instructions
- In `prompt_context.py`, implement `render_decomposition_contract(agent_role, next_id)` for `requirement-agent` and `planner-agent`, update `Semantic Review Rubric` for `review-agent`, and append `### Existing Requirements Catalog` in `render_target_context_section` when `target_document.artifact_type == "INT"` and `REQ`s exist.
- In `prompt_builder.py`, call `render_decomposition_contract` in `_assemble_prompt_sections`.
