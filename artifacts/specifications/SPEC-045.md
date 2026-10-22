---
id: SPEC-045
title: Expanded Task File Budgets and Single-Concern Test Separation Specification
status: approved
traces_to:
- REQ-045
covers_criteria:
- REQ-045:AC-01
- REQ-045:AC-02
- REQ-045:AC-03
decisions: []
target_files:
  tests:
  - tests/test_checkers.py
  - tests/test_schemas_checker.py
  - tests/test_clean_code_checker.py
  - tests/test_architecture_checker.py
  - tests/test_traceability_checker.py
  - tests/test_cli.py
  - tests/test_orchestrator.py
  - tests/test_interaction_logging.py
  - tests/test_stage_runner.py
  - tests/test_prompt_builder.py
  - tests/test_documentation_generator.py
  - tests/test_review_gates.py
  - tests/test_lifecycle.py
  - tests/test_task_runner.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
Configure `TASK.max_write_files: 8` and `TASK.max_required_files: 10` (plus matching `json_schema` `maxItems`) in `policy/schemas.yaml`, superseding `REQ-019` and `SPEC-019`. Update `render_decomposition_contract` in `src/multi_tasker/orchestrator/prompt_context.py` so `planner-agent` authors single-concern `TestContract` and `implementation` `Task` artifacts without compound `_and_` test filenames. Split mixed test modules into single-concern `tests/test_*.py` files below `400` lines and remove `tests/test_traceability_and_cli.py` and `tests/test_transitions_and_execution.py`.

## Public Interfaces
```python
# src/multi_tasker/orchestrator/prompt_context.py
def render_decomposition_contract(agent_role: str, next_id: str | None) -> list[str]:
    """Render Requirement or Planner decomposition contract for agent_role."""
```

## Test Contract Mapping
- `REQ-045:AC-01` -> `tests/test_schemas_checker.py::test_aligned_policy_limits_and_prompt_artifact_constraints`
- `REQ-045:AC-02` -> `tests/test_prompt_builder.py::test_planner_single_concern_decomposition_contract`
- `REQ-045:AC-03` -> `tests/test_task_runner.py::test_modular_refactoring_and_file_size_ceilings`
