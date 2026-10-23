---
id: TASK-138
title: Implement ANSI C and Rust Presets, Lineage Traces, and Role Prompt Synthesis
type: implementation
status: done
traces_to:
- REQ-052
- SPEC-052
depends_on:
- TASK-136
- TASK-137
required_files:
- tests/test_multi_language_pipeline.py
- src/multi_tasker/checkers/language_support.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
write_files:
- src/multi_tasker/orchestrator/language_presets.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_pipeline.py
---
## Objective
Add `src/multi_tasker/orchestrator/language_presets.py` and update `lifecycle.py`, `lineage.py`, `prompt_builder.py`, and `prompt_context.py` for `ansi-c` and `rust`.

## Scoped Instructions
- Create `src/multi_tasker/orchestrator/language_presets.py` with `VALID_PRESETS = ("python", "ansi-c", "rust", "multi-tasker")`, preset policy scaffolding for `ansi-c` and `rust`, and language-specific `TestContract` prompt blocks and code fence helpers.
- Update `lifecycle.py` to apply language preset policies in `initialize_repository`, `lineage.py` to collect non-Python `@traces` links, and `prompt_builder.py` and `prompt_context.py` to render language-specific code contracts and fences.
