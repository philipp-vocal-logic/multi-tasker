---
id: TASK-078
title: Implement Self-Contained Role Prompts and Remove Context Mode Split
type: implementation
status: done
traces_to:
- REQ-028
- SPEC-028
depends_on:
- TASK-077
required_files:
- tests/test_interaction_logging.py
write_files:
- src/multi_tasker/checkers/permissions_checker.py
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py
---
## Objective
Remove `context_mode` branching and implement the self-contained 3-step `Execution Steps` and `Architecture Layers` in `prompt_builder.py`, `stage_runner.py`, `main.py`, and `permissions_checker.py`.

## Scoped Instructions
Update `src/multi_tasker/orchestrator/prompt_builder.py`, `src/multi_tasker/orchestrator/stage_runner.py`, `src/multi_tasker/cli/main.py`, and `src/multi_tasker/checkers/permissions_checker.py`.
