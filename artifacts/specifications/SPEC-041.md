---
id: SPEC-041
title: Orchestrator Lifecycle Decomposition and Escalation Router Specification
status: approved
traces_to:
- REQ-041
covers_criteria:
- REQ-041:AC-01
- REQ-041:AC-02
- REQ-041:AC-03
decisions: []
target_files:
  tests:
  - tests/test_stage_escalation.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/cli/main.py
---
## Design Overview
Move `_create_review_escalation`, `evaluate_review_verdict`, and `resolve_escalation` from `src/multi_tasker/orchestrator/lifecycle.py` into `src/multi_tasker/orchestrator/router.py`, and expose `check_transition` and `mark_dirty_downstream` in `lifecycle.py` for reuse by `router.py`. Update `src/multi_tasker/cli/main.py` and `src/multi_tasker/orchestrator/stage_runner.py` to import `resolve_escalation` and `evaluate_review_verdict` directly from `multi_tasker.orchestrator.router`, bringing `lifecycle.py` below `400` lines.

## Public Interfaces
```python
def check_transition(
    repository_root: Path, document: ArtifactDocument, target_state: str
) -> list[Finding]:
    """Validate artifact status transition against schemas or permissions policy."""


def mark_dirty_downstream(repository_root: Path, changed_id: str) -> list[str]:
    """Transition downstream SPEC/TASK to needs_update and sync upstream Intents."""


def evaluate_review_verdict(
    repository_root: Path, artifact_id: str, rev_id: str
) -> list[Finding]:
    """Check REV verdict for artifact_id and emit Finding or escalation on fail."""


def resolve_escalation(
    repository_root: Path, escalation_id: str, resolved_by: str
) -> list[Finding]:
    """Resolve an Escalation with a Decision or Task and propagate dirty flags."""
```

## Test Contract Mapping
- `REQ-041:AC-01` -> `tests/test_stage_escalation.py::test_lifecycle_decomposition_and_router_cohesiveness`
- `REQ-041:AC-02` -> `tests/test_stage_escalation.py::test_lifecycle_decomposition_and_router_cohesiveness`
- `REQ-041:AC-03` -> `tests/test_stage_escalation.py::test_lifecycle_decomposition_and_router_cohesiveness`
