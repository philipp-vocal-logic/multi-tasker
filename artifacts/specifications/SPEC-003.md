---
id: SPEC-003
title: CLI Lifecycle, Lineage, and Live Documentation Specification
status: approved
traces_to: [REQ-003]
covers_criteria:
  - REQ-003:AC-01
  - REQ-003:AC-02
  - REQ-003:AC-03
  - REQ-003:AC-04
decisions: []
target_files:
  tests:
    - tests/test_lifecycle.py
  implementation:
    - src/orchestrator/lifecycle.py
    - src/orchestrator/lineage.py
    - src/orchestrator/documentation_generator.py
    - src/cli/output.py
    - src/cli/main.py
---
## Design Overview
Implement `src/orchestrator/lifecycle.py` for repository initialization (`initialize_repository`), `Intent` creation, `Requirement`/`Decision` approval, `Escalation` resolution, and parallel `Worktree` `Task` execution (`run_scheduled_tasks`), `src/orchestrator/lineage.py` for `trace_lineage`, and `src/orchestrator/documentation_generator.py` for live specification generation (`generate_repository_documentation`).

## Public Interfaces
```python
def initialize_repository(repository_root: Path) -> list[Finding]: ...
def create_intent(repository_root: Path, text_or_file: str, timestamp: str | None = None) -> str: ...
def approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]: ...
def resolve_escalation(repository_root: Path, escalation_id: str, resolved_by: str) -> list[Finding]: ...
def run_scheduled_tasks(repository_root: Path, max_workers: int = 1, agent_command: str | None = None) -> tuple[list[str], list[Finding]]: ...
def trace_lineage(repository_root: Path, target: str) -> list[str]: ...
def generate_repository_documentation(repository_root: Path) -> str: ...
```

## Test Contract Mapping
- `test_initialize_and_intent_creation_with_git` -> `REQ-003:AC-01`
- `test_approve_and_resolve_dirty_propagation` -> `REQ-003:AC-02`
- `test_run_scheduled_tasks_worktree_execution` -> `REQ-003:AC-03`
- `test_trace_lineage_and_documentation_generation` -> `REQ-003:AC-04`
