---
id: TASK-034
title: Implement Context Mode Policy Validation and Prompt Synthesis Modes
type: implementation
status: done
traces_to:
- REQ-012
- SPEC-012
depends_on:
- TASK-033
required_files:
- tests/test_interaction_logging.py
write_files:
- src/checkers/permissions_checker.py
- src/orchestrator/prompt_builder.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Validate `default_context_mode` in `src/checkers/permissions_checker.py` and implement `inline` and `paths` prompt synthesis in `src/orchestrator/prompt_builder.py`.

## Scoped Instructions
Update `_validate_execution_environments` in `src/checkers/permissions_checker.py` to validate `default_context_mode` (`inline` or `paths`). Implement `resolve_context_mode`, `prepare_worker_invocation`, and `context_mode`-aware `build_agent_prompt` in `src/orchestrator/prompt_builder.py` so `inline` embeds full schemas, `forbidden_synonyms`, upstream artifacts, and existing `required_files`/`write_files` contents while `paths` emits path pointers.
