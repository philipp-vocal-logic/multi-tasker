---
id: SPEC-008
title: Atomic Approval Validation and Clean Failed Task Execution Specification
status: approved
traces_to:
- REQ-008
covers_criteria:
- REQ-008:AC-01
- REQ-008:AC-02
decisions: []
target_files:
  tests:
  - tests/test_orchestrator.py
  implementation:
  - src/orchestrator/lifecycle.py
---
## Design Overview
Run `run_checks(repository_root, ["glossary", "schemas"], target_paths=[document.path])` in `approve_artifact` (`src/orchestrator/lifecycle.py`) before calling `update_artifact_frontmatter` so any validation failure returns Findings without mutating the file on disk. In `_finalize_task_outcome` (`src/orchestrator/lifecycle.py`), remove the redundant `update_artifact_frontmatter(absolute_task, {"status": previous_status})` call on failure so `BaseBranch` `Task` files remain byte-for-byte unchanged and Git status stays clean when a `Worktree` fails the `MergeGate`.

## Public Interfaces
```python
def approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]: ...
```

## Test Contract Mapping
- `test_atomic_approve_and_failed_run_preserve_clean_base` -> `REQ-008:AC-01`, `REQ-008:AC-02`
