---
id: TASK-114
title: Update Planner Decomposition Contract for Single-Concern Test Modules
type: implementation
status: ready
traces_to:
  - REQ-045
  - SPEC-045
depends_on:
  - TASK-111
  - TASK-112
  - TASK-113
required_files:
  - tests/test_schemas_checker.py
  - tests/test_prompt_builder.py
  - tests/test_task_runner.py
  - src/multi_tasker/orchestrator/prompt_context.py
write_files:
  - src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: "pytest -q tests/test_schemas_checker.py tests/test_prompt_builder.py tests/test_task_runner.py"
---
## Objective
Update `render_decomposition_contract` in `src/multi_tasker/orchestrator/prompt_context.py` so `planner-agent` decomposes multi-concern specifications into single-concern tasks without `_and_` test filenames.

## Scoped Instructions
In `src/multi_tasker/orchestrator/prompt_context.py`, update the `planner-agent` branch of `render_decomposition_contract` to instruct authoring single-concern `type: test_contract` Task(s) (`write_files` covering `SPEC` `target_files.tests` without compound `_and_` test filenames) and `type: implementation` Task(s).
