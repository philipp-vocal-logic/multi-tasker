---
id: TASK-132
title: Enforce Unknown Execution Env Guard and Policy-Only Escalation Routes
type: implementation
status: planned
traces_to:
- REQ-050
- SPEC-050
depends_on:
- TASK-130
- TASK-131
required_files:
- tests/test_orchestrator.py
- tests/test_stage_runner.py
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/orchestrator/task_runner.py
write_files:
- src/multi_tasker/orchestrator/router.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/orchestrator/task_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_orchestrator.py tests/test_stage_runner.py
  tests/test_task_runner.py tests/test_prompt_builder.py
---
## Objective
Remove `CATEGORY_ROUTES` from `router.py` and `prompt_builder.py`, and emit `CLI_UNKNOWN_EXEC_ENV` when an unresolvable execution environment is requested in `stage_runner.py` or `task_runner.py`.

## Scoped Instructions
- In `src/multi_tasker/orchestrator/router.py`, delete `CATEGORY_ROUTES` and read `escalation_routes` exclusively from `load_pipeline_policy(repository_root)`.
- In `src/multi_tasker/orchestrator/prompt_context.py` and `src/multi_tasker/orchestrator/prompt_builder.py`, include `load_pipeline_policy(repository_root)` in `load_artifact_schemas_and_limits` and render escalation routes from policy instead of `CATEGORY_ROUTES`.
- In `src/multi_tasker/orchestrator/stage_runner.py` and `src/multi_tasker/orchestrator/task_runner.py`, emit `Finding("policy/agent_execution.yaml", 1, "CLI_UNKNOWN_EXEC_ENV", ...)` when a requested execution environment cannot be resolved.
