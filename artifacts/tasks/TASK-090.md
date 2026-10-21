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
- src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: pytest -q tests/test_interaction_logging.py
---
## Objective
Extract `src/multi_tasker/orchestrator/prompt_context.py` and implement non-fixed prompt example IDs (`<TYPE>-NNN`, `ESC-NNN`, `AC-XX`), 88-character line wrapping (`MAX_PROMPT_LINE_LENGTH = 88`), `max_line_length=88` in `WorkerAgent` `Source Limits`, and canonical `Glossary Terms` rendering.

## Scoped Instructions
1. Create `src/multi_tasker/orchestrator/prompt_context.py` with `MAX_PROMPT_LINE_LENGTH = 88`, `wrap_prompt_lines`, `render_code_and_glossary_section` (including `max_line_length=88` and `Glossary Terms`), and `render_target_context_section`.
2. Update `src/multi_tasker/orchestrator/prompt_builder.py` to use `prompt_context` and emit non-fixed `<TYPE>-NNN`, `ESC-NNN`, and `AC-XX` in schema skeletons, `ESC` contracts, and targetless role prompts.
