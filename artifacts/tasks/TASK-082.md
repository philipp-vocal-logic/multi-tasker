---
id: TASK-082
title: Implement Decorator Prompt Guidance and Pipeline Worker Environment Default
type: implementation
status: ready
traces_to:
- REQ-030
- SPEC-030
depends_on:
- TASK-081
required_files:
- tests/test_interaction_logging.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py tests/test_stage_runner.py
---
## Objective
Add 3-argument `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` prompt guidance in `prompt_builder.py` and pass `options[2] or "agy"` in `_step_declarative_stage` in `stage_runner.py`.

## Scoped Instructions
Update `_render_code_and_glossary_section` and `_assemble_prompt_sections` in `src/multi_tasker/orchestrator/prompt_builder.py` and `_step_declarative_stage` in `src/multi_tasker/orchestrator/stage_runner.py`.
