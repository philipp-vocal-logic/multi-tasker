---
id: SPEC-002
title: Orchestrator Worktree, MergeGate, Scheduler, and Router Specification
status: approved
traces_to: [REQ-002]
covers_criteria:
  - REQ-002:AC-01
  - REQ-002:AC-02
  - REQ-002:AC-03
  - REQ-002:AC-04
decisions: []
target_files:
  tests:
    - tests/test_orchestrator.py
  implementation:
    - src/orchestrator/worktree.py
    - src/orchestrator/merge_gate.py
    - src/orchestrator/scheduler.py
    - src/orchestrator/router.py
---
## Design Overview
Implement `worktree.py` for SHA-256 `policy/` verification and read-only `Worktree` creation, `merge_gate.py` for deterministic `MergeGate` evaluation, `scheduler.py` for conflict-free parallel `Task` batching and dirty-flagging, and `router.py` for tiered `Escalation` routing.

## Public Interfaces
```python
def compute_policy_sha256(repository_root: Path) -> str: ...
def verify_clean_repository(repository_root: Path, expected_policy_sha256: str | None = None) -> list[Finding]: ...
def create_worktree(repository_root: Path, run_id: str, base_reference: str = "HEAD") -> Path: ...
def commit_traceable_change(repository_root: Path, relative_paths: list[str], commit_message: str) -> bool: ...
def evaluate_merge_gate(request: GateRequest) -> GateOutcome: ...
def select_parallel_batch(repository_root: Path, active_write_locks: set[str] | None = None) -> tuple[list[str], set[str]]: ...
def compute_dirty_subgraph(repository_root: Path, changed_id: str) -> list[str]: ...
def route_escalation(repository_root: Path, escalation_relative_path: str, prior_reroutes: int = 0) -> RouteDecision: ...
```

## Test Contract Mapping
- `test_worktree_lifecycle_and_clean_repo_checks` -> `REQ-002:AC-01`
- `test_merge_gate_enforces_tamper_perms_escalation_and_cmd` -> `REQ-002:AC-02`
- `test_parallel_scheduler_and_dirty_subgraph` -> `REQ-002:AC-03`
- `test_escalation_router_and_loop_prevention` -> `REQ-002:AC-04`
