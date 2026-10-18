---
id: TASK-063
title: Add TestContract for Pipeline Suitability Evaluation and Per-Role Stage Telemetry
type: test_contract
status: done
traces_to:
- REQ-022
- SPEC-022
depends_on: []
required_files:
- tests/test_stage_runner.py
- tests/test_interaction_logging.py
write_files:
- tests/test_stage_runner.py
- tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_stage_runner.py tests/test_interaction_logging.py
---
## Objective
Add `test_pipeline_suitability_evaluation_and_per_role_telemetry` in `tests/test_interaction_logging.py` and streamline `tests/test_stage_runner.py` to stay under the `400`-line refactoring threshold.

## Scoped Instructions
- In `tests/test_interaction_logging.py`, add `test_pipeline_suitability_evaluation_and_per_role_telemetry` decorated with `@traces("REQ-022", "AC-01", "SPEC-022")` and `@traces("REQ-022", "AC-02", "SPEC-022")` to verify `mt run --evaluate` in a new repository, custom `app` package `PYTHONPATH` verification, per-role `agent_role` telemetry, and JSON suitability summary output.
- In `tests/test_stage_runner.py`, use `bootstrap_evaluation_repository` to keep the module below `400` lines.
