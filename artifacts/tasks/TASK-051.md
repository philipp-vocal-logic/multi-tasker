---
id: TASK-051
title: Keep Worktree PYTHONPATH Expression Single-Line in prompt_builder and stage_runner
type: implementation
status: done
traces_to:
- REQ-016
- SPEC-016
depends_on:
- TASK-050
required_files:
- tests/test_interaction_logging.py
- src/orchestrator/prompt_builder.py
- src/orchestrator/stage_runner.py
write_files:
- src/orchestrator/prompt_builder.py
- src/orchestrator/stage_runner.py
verification_cmd: pytest -q tests/test_transitions_and_execution.py tests/test_interaction_logging.py
---
## Objective
Format `PYTHONPATH` in `src/orchestrator/prompt_builder.py` and `src/orchestrator/stage_runner.py` so `src/orchestrator/prompt_builder.py` stays at or below 360 lines.

## Scoped Instructions
Update `prepare_worker_invocation` in `src/orchestrator/prompt_builder.py` and `_prepare_stage_invocation` in `src/orchestrator/stage_runner.py` to format `PYTHONPATH` using `Path(__file__).parents[2]` on a single line so `test_modular_refactoring_and_file_size_ceilings` passes.
