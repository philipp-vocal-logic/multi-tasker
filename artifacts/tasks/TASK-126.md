---
id: TASK-126
title: Update Orchestrator and CLI Main for Separated Policy Files
type: implementation
status: ready
traces_to:
- REQ-048
- SPEC-048
depends_on:
- TASK-123
- TASK-124
- TASK-125
required_files:
- tests/test_lifecycle.py
- tests/test_stage_runner.py
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/documentation_generator.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/orchestrator/worktree.py
write_files:
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/documentation_generator.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/stage_runner.py
- src/multi_tasker/orchestrator/worktree.py
verification_cmd: pytest -o pythonpath=src -q tests/test_schemas_checker.py tests/test_lifecycle.py
  tests/test_stage_runner.py tests/test_task_runner.py tests/test_review_gates.py
  tests/test_pipeline_combinations.py
---
## Objective
Update `Orchestrator` modules and `cli/main.py` to read and scaffold the concern-separated `policy/*.yaml` files.

## Scoped Instructions
Update `worktree.py`, `merge_gate.py`, `stage_runner.py`, `cli/main.py`, `prompt_builder.py`, `prompt_context.py`, `lifecycle.py`, and `documentation_generator.py` to reference `agent_permissions.yaml`, `agent_execution.yaml`, `artifact_schemas.yaml`, `artifact_limits.yaml`, `artifact_lifecycle.yaml`, `code_architecture.yaml`, `code_limits.yaml`, and `code_quality.yaml`.
