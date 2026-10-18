---
id: TASK-066
title: Implement Programmatic Artifact ID Normalization, Prompt Hints, and Deferred
  TestContract Check
type: implementation
status: done
traces_to:
- REQ-023
- SPEC-023
depends_on:
- TASK-065
required_files:
- artifacts/specifications/SPEC-023.md
- tests/test_checkers.py
write_files:
- src/domain/parser.py
- src/checkers/code_and_git_traceability.py
- src/orchestrator/prompt_builder.py
verification_cmd: python3 -m py_compile src/domain/parser.py src/checkers/code_and_git_traceability.py
  src/orchestrator/prompt_builder.py
---
## Objective
Implement `next_artifact_id` and `normalize_new_stage_artifacts` in `src/domain/parser.py`, defer `TRACE_MISSING_TEST_CONTRACT` for planned `TestContract` `Tasks` in `src/checkers/code_and_git_traceability.py`, and render assigned IDs and stage/planner execution rules in `src/orchestrator/prompt_builder.py`.

## Scoped Instructions
Keep all modified files under 400 lines and all functions within configured clean code limits.
