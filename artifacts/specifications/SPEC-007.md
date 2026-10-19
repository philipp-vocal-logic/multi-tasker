---
id: SPEC-007
title: Specification Approval and Exhaustive State Transition Testing Specification
status: approved
traces_to:
  - REQ-007
covers_criteria:
  - REQ-007:AC-01
  - REQ-007:AC-02
decisions: []
target_files:
  tests:
    - tests/test_orchestrator.py
  implementation:
    - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Extend `approve_artifact` in `src/multi_tasker/orchestrator/lifecycle.py` so `SPEC-NNN` (`Specification`) artifacts in `draft` or `in_review` state can be approved via `mt approve`, validating `glossary` and `schemas` checks and marking downstream `done` `Task` artifacts as `needs_update`. Add data-driven tests in `tests/test_orchestrator.py` that iterate over all agent roles in `policy/permissions.yaml` and state transitions in `policy/schemas.yaml` to verify every `(agent_role, existing_state, target_state)` combination and CLI approval transition.

## Public Interfaces
```python
def approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]: ...
```

## Test Contract Mapping
- `test_approve_specification_and_dirty_task_propagation` -> `REQ-007:AC-01`
- `test_exhaustive_agent_and_lifecycle_state_transitions` -> `REQ-007:AC-02`
