---
id: TASK-035
title: Wire CLI Context Mode Flag into Prompt Subcommand and Worktree Task Runner
type: implementation
status: done
traces_to:
- REQ-012
- SPEC-012
depends_on:
- TASK-033
- TASK-034
required_files:
- tests/test_interaction_logging.py
- src/multi_tasker/orchestrator/prompt_builder.py
write_files:
- src/multi_tasker/orchestrator/task_runner.py
- src/multi_tasker/cli/main.py
verification_cmd: pytest -q
---
## Objective
Wire `--context-mode` into `mt prompt` and `mt run` in `src/multi_tasker/cli/main.py` and delegate `Worktree` prompt/environment setup in `src/multi_tasker/orchestrator/task_runner.py`.

## Scoped Instructions
Add `--context-mode` to `prompt` and `run` subcommands in `src/multi_tasker/cli/main.py`, pass `context_mode` to `build_agent_prompt` and `run_scheduled_tasks`, and update `src/multi_tasker/orchestrator/task_runner.py` to use `prepare_worker_invocation` from `src/multi_tasker/orchestrator/prompt_builder.py` so `Worktree` runs synthesize prompts in the resolved mode and export `MT_CONTEXT_MODE`.
