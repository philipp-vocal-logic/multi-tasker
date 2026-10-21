---
id: SPEC-038
title: Subgraph-Scoped Traceability Checks for Multi-Requirement Stages Specification
status: approved
traces_to:
- REQ-038
covers_criteria:
- REQ-038:AC-01
- REQ-038:AC-02
- REQ-038:AC-03
decisions: []
target_files:
  tests:
  - tests/test_traceability_and_cli.py
  implementation:
  - src/multi_tasker/checkers/traceability_checker.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
---
## Design Overview
In `traceability_checker.py`, pass `target_paths` to `_check_requirement_to_specification_coverage(by_identifier, target_paths)`. When `target_paths` contains only `artifacts/specifications/**` or `artifacts/tasks/**` paths, restrict checked `REQ`s to those referenced in `traces_to` by the targeted `SPEC`/`TASK` documents (or all `REQ`s when `target_paths` is `None` or includes `src/`/`tests/`). Similarly, in `code_and_git_traceability.py`, restrict `TRACE_UNPLANNED_TARGET_FILE` to `SPEC`s referenced by targeted `TASK`/`SPEC` documents when `target_paths` is artifact-scoped.

## Public Interfaces
```python
def check_traceability(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/traceability.yaml and stage-aware bidirectional traceability."""


def check_specification_target_files(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    target_paths: list[str] | None,
    rules: dict[str, Any],
) -> list[Finding]:
    """Verify target_files declarations on disk and in TASK write_files."""
```

## Test Contract Mapping
- `REQ-038:AC-01`: `tests/test_traceability_and_cli.py::test_scoped_multi_req_and_spec_traceability_checks` verifies scoped `SPEC-001` and `TASK-001` checks pass while sibling `REQ-002` and `SPEC-002` are pending.
- `REQ-038:AC-02`: `tests/test_traceability_and_cli.py::test_scoped_multi_req_and_spec_traceability_checks` verifies `target_paths=None` flags uncovered sibling `REQ-002` and `SPEC-002`.
- `REQ-038:AC-03`: `tests/test_traceability_and_cli.py::test_scoped_multi_req_and_spec_traceability_checks` verifies scoped `SPEC-001` check emits `TRACE_UNCOVERED_REQ_AC` if `SPEC-001` omits an `AC` of its own `REQ-001`.
