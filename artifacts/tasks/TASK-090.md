---
id: TASK-090
title: Implement Non-Fixed Prompt Example IDs, 88-Char Line Wrapping, and Glossary Terms
type: implementation
status: ready
traces_to:
- REQ-034
- SPEC-034
depends_on:
- TASK-089
required_files:
- artifacts/requirements/REQ-034.md
- artifacts/specifications/SPEC-034.md
- tests/test_interaction_logging.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
verification_cmd: pytest -q tests/test_interaction_logging.py
---
## Objective
Implement non-fixed prompt example IDs (`<TYPE>-NNN`, `ESC-NNN`, `AC-XX`), 88-character line wrapping (`MAX_PROMPT_LINE_LENGTH = 88`), `max_line_length=88` in `WorkerAgent` `Source Limits`, and canonical `Glossary Terms` rendering in `src/multi_tasker/orchestrator/prompt_builder.py`.

## Scoped Instructions
1. Update `_format_property_hint`, `_render_artifact_schema_block`, `_render_escalation_contract`, and `_assemble_prompt_sections` in `src/multi_tasker/orchestrator/prompt_builder.py` so templates and `ESC` contracts use non-fixed `<TYPE>-NNN`, `ESC-NNN`, and `AC-XX`, and targetless prompts use `<TYPE>-NNN`.
2. Add `MAX_PROMPT_LINE_LENGTH = 88` and wrap synthesized prompt instruction lines (Sections 1 to 3) to `<= 88` characters, add `max_line_length=88` to `WorkerAgent` `Source Limits`, and render canonical `Glossary Terms` (`canonical` and `code_identifiers`) in `_render_glossary_constraints`.
