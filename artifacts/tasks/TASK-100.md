---
id: TASK-100
title: Implement Requirement Supersession and Deprecation Lifecycle
type: implementation
status: ready
traces_to:
  - REQ-039
  - SPEC-039
depends_on:
  - TASK-099
required_files:
  - tests/test_lifecycle.py
  - artifacts/requirements/REQ-039.md
  - artifacts/specifications/SPEC-039.md
write_files:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/checkers/traceability_checker.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/lineage.py
verification_cmd: pytest -o pythonpath=src -q tests/test_lifecycle.py -k requirement_supersession
---
## Objective
Implement `supersedes` auto-deprecation in `lifecycle.py`, `deprecated` upstream reference checks in `traceability_checker.py`, and `deprecated` `Requirement` filtering in `prompt_context.py` and `lineage.py`.

## Scoped Instructions
Update `_mark_dirty_downstream` and `_sync_upstream_intents` in `lifecycle.py` with `_deprecate_superseded_requirements`, update `LIST_REFERENCE_FIELDS` and `_check_document_references` in `traceability_checker.py`, update `render_decomposition_contract` and `_render_existing_requirements_catalog` in `prompt_context.py`, and filter `deprecated` `Requirement` artifacts in `_compute_static_test_metrics` and `_referenced_artifact_ids` in `lineage.py`.
