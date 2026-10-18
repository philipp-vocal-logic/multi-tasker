---
id: TASK-065
title: Add TestContract for Programmatic ID Normalization and Streamlined Pipeline
type: test_contract
status: done
traces_to:
- REQ-023
- SPEC-023
depends_on: []
required_files:
- artifacts/requirements/REQ-023.md
- artifacts/specifications/SPEC-023.md
write_files:
- tests/test_checkers.py
verification_cmd: python3 -m py_compile tests/test_checkers.py
---
## Objective
Add `test_programmatic_id_normalization_and_streamlined_pipeline_checks` decorated with `@traces("REQ-023", "AC-01", "SPEC-023")` and `@traces("REQ-023", "AC-02", "SPEC-023")` in `tests/test_checkers.py`.

## Scoped Instructions
Verify `next_artifact_id`, `normalize_new_stage_artifacts` (renumbering colliding `TASK-001` and `TASK-002` with `depends_on` preservation), prompt instructions (`Assigned Next Artifact ID`, `--agent`, `Planner Decomposition Contract`), stage-aware `check_test_contract_coverage` with planned `TestContract` `Tasks`, and `stage_runner` timeout/review handling.
