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
- src/domain/parser.py
- src/checkers/traceability_checker.py
- src/orchestrator/documentation_generator.py
write_files:
- src/domain/parser.py
- src/checkers/traceability_checker.py
- src/orchestrator/documentation_generator.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Validate `max_review_cycles` in `src/domain/parser.py`, add `target_artifacts` reference checking in `src/checkers/traceability_checker.py`, and render `REV-*` Mermaid edges in `src/orchestrator/documentation_generator.py`.

## Scoped Instructions
Enforce `max_review_cycles >= 1` in `validate_pipeline_policy` in `src/domain/parser.py`, include `"target_artifacts"` in `LIST_REFERENCE_FIELDS` in `src/checkers/traceability_checker.py`, and render `REV-*` verdict labels and `target_artifacts` dotted edges in `src/orchestrator/documentation_generator.py`.
