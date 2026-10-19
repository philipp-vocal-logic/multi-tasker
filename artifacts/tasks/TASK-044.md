---
id: TASK-044
title: Implement Pipeline Bounds Check, Review Traceability, and Mermaid Review Edges
type: implementation
status: done
traces_to:
- REQ-015
- SPEC-015
depends_on:
- TASK-043
required_files:
- tests/test_stage_runner.py
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/traceability_checker.py
- src/multi_tasker/orchestrator/documentation_generator.py
write_files:
- src/multi_tasker/domain/parser.py
- src/multi_tasker/checkers/traceability_checker.py
- src/multi_tasker/orchestrator/documentation_generator.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Validate `max_review_cycles` in `src/multi_tasker/domain/parser.py`, add `target_artifacts` reference checking in `src/multi_tasker/checkers/traceability_checker.py`, and render `REV-*` Mermaid edges in `src/multi_tasker/orchestrator/documentation_generator.py`.

## Scoped Instructions
Enforce `max_review_cycles >= 1` in `validate_pipeline_policy` in `src/multi_tasker/domain/parser.py`, include `"target_artifacts"` in `LIST_REFERENCE_FIELDS` in `src/multi_tasker/checkers/traceability_checker.py`, and render `REV-*` verdict labels and `target_artifacts` dotted edges in `src/multi_tasker/orchestrator/documentation_generator.py`.
