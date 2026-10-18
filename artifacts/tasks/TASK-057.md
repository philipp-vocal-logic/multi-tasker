---
id: TASK-057
title: Implement Aligned Function Limit Defaults and Prompt Artifact Constraint Rendering
type: implementation
status: planned
traces_to:
- REQ-019
- SPEC-019
depends_on:
- TASK-056
required_files:
- tests/test_checkers.py
- src/checkers/limits_checker.py
- src/orchestrator/prompt_builder.py
write_files:
- src/checkers/limits_checker.py
- src/orchestrator/prompt_builder.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Update default `max_function_lines` (`50`) and `max_function_args` (`6`) in `src/checkers/limits_checker.py` and render top-level `artifacts.<TYPE>` limits and `single_paragraph_only` section rules in `src/orchestrator/prompt_builder.py`.

## Scoped Instructions
In `src/checkers/limits_checker.py`, update `_check_ast_node_limits` fallback defaults to `max_function_lines=50` and `max_function_args=6`. In `src/orchestrator/prompt_builder.py`, extract or update `_render_artifact_schema_block` (keeping McCabe complexity <= 8) so that for any `artifact_type`, every key in `artifacts.<TYPE>` other than `required_sections` and `sections` is rendered as `- **Artifact Limit \`<key>\`**: \`<val>\``, and any section in `artifacts.<TYPE>.sections` with `single_paragraph_only: true` appends `, single paragraph only` to its `- Section \`## <name>\`: ...` line.
