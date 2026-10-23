---
id: TASK-141
title: Harden Presets, Review Prompt Scope, Worktree Report Directory, and Lineage
  Coverage
type: implementation
status: ready
traces_to:
- REQ-053
- SPEC-053
depends_on:
- TASK-139
- TASK-140
required_files:
- tests/test_multi_language_greenfield_hardening.py
- src/multi_tasker/orchestrator/language_presets.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/worktree.py
write_files:
- src/multi_tasker/orchestrator/language_presets.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/worktree.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_greenfield_hardening.py tests/test_multi_language_pipeline.py
---
## Objective
Harden preset architecture/verification policies, `review-agent` prompt paths, worktree `.report` creation, and language-aware prompt context and documentation.

## Scoped Instructions
- Update `lifecycle.py` and `language_presets.py` so `domain` and `services` allow `src` internal imports while forbidding upward layer imports, and C/Rust `impl_cmd` pre-creates `.report` and compiles C sources under `src/`.
- Update `prompt_builder.py` (`_resolve_stage_write_paths`) so `write_files` only applies to `worker-agent`, and `prompt_context.py` so `TestContract Decorator` is language-aware.
- Update `worktree.py` (`create_worktree`) to create `.report`, and `lineage.py` (`collect_pytest_line_coverage`) to run `pytest` only when `language == "python"`.
