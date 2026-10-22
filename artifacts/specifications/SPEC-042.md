---
id: SPEC-042
title: Stage-Agent Escalation Persistence and BaseBranch Routing Specification
status: approved
traces_to:
- REQ-042
covers_criteria:
- REQ-042:AC-01
- REQ-042:AC-02
- REQ-042:AC-03
decisions: []
target_files:
  tests:
  - tests/test_stage_escalation.py
  implementation:
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Add `finalize_stage_escalation` in `src/multi_tasker/orchestrator/router.py` and invoke it from `_finalize_stage_outcome` in `src/multi_tasker/orchestrator/stage_runner.py` when `outcome.escalated` and `outcome.escalation_path` are truthy. `finalize_stage_escalation` copies the `Escalation` file from `Worktree` to `BaseBranch`, routes it via `route_escalation`, transitions `REQ`/`SPEC`/`TASK` targets to `blocked` (leaving `INT` in `open`), commits a traceable change, and returns a `GATE_TASK_ESCALATED` `Finding`.

## Public Interfaces
```python
def finalize_stage_escalation(
    repository_root: Path,
    worktree_path: Path,
    target_id: str,
    escalation_path: str,
) -> tuple[list[str], list[Finding]]:
    """Merge a stage Escalation onto BaseBranch, route it, and block target_id."""
```

## Test Contract Mapping
- `REQ-042:AC-01` -> `tests/test_stage_escalation.py::test_stage_agent_escalation_persistence_routing_and_rejection`
- `REQ-042:AC-02` -> `tests/test_stage_escalation.py::test_stage_agent_escalation_persistence_routing_and_rejection`
- `REQ-042:AC-03` -> `tests/test_stage_escalation.py::test_stage_agent_escalation_persistence_routing_and_rejection`
