---
id: SPEC-039
title: Requirement Supersession and Deprecation Lifecycle Specification
status: approved
traces_to:
- REQ-039
covers_criteria:
- REQ-039:AC-01
- REQ-039:AC-02
- REQ-039:AC-03
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/checkers/traceability_checker.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/lineage.py
---
## Design Overview
Extend `approve_artifact` in `src/multi_tasker/orchestrator/lifecycle.py` with `_deprecate_superseded_requirements` so approving a `Requirement` with `supersedes: [REQ-NNN]` transitions each superseded `approved` `Requirement` and any `approved` `Specification` tracing exclusively to `deprecated` `Requirement` artifacts into `status: deprecated`, while `_sync_upstream_intents` treats `approved` and `deprecated` `Requirement` artifacts as completed. Update `src/multi_tasker/checkers/traceability_checker.py` to validate `supersedes` references and allow `deprecated` upstreams for `deprecated` `Specification` and `done` `Task` artifacts. Update `src/multi_tasker/orchestrator/prompt_context.py` and `src/multi_tasker/orchestrator/lineage.py` to exclude `deprecated` `Requirement` artifacts from the active catalog and static `AcceptanceCriterion` count.

## Public Interfaces
```python
# src/multi_tasker/orchestrator/lifecycle.py
def _deprecate_superseded_requirements(
    repository_root: Path,
    changed_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> None: ...
```

## Test Contract Mapping
- `REQ-039:AC-01` -> `tests/test_lifecycle.py::test_requirement_supersession_deprecates_old_req_and_spec`
- `REQ-039:AC-02` -> `tests/test_lifecycle.py::test_requirement_supersession_deprecates_old_req_and_spec`
- `REQ-039:AC-03` -> `tests/test_lifecycle.py::test_requirement_supersession_deprecates_old_req_and_spec`
