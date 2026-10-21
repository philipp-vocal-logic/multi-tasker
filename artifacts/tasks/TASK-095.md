---
id: TASK-095
title: Add TestContracts for Multi-REQ Intent Completion and Multi-Artifact Review
type: test_contract
status: done
traces_to:
- REQ-037
- SPEC-037
depends_on: []
required_files:
- artifacts/requirements/REQ-037.md
- artifacts/specifications/SPEC-037.md
- tests/test_lifecycle.py
- tests/test_stage_runner.py
write_files:
- tests/test_lifecycle.py
- tests/test_stage_runner.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py tests/test_stage_runner.py
---
## Objective
Add `@traces("REQ-037", ...)` TestContracts in `tests/test_lifecycle.py` and `tests/test_stage_runner.py` verifying `INT` transitions to `processing` when sibling `REQ`s remain unapproved, transitions to `processed` when all linked `REQ`s are approved, and reviews all produced stage artifacts.

## Scoped Instructions
- In `tests/test_lifecycle.py`, add `test_multi_requirement_intent_processing_and_completion` with `@traces("REQ-037", "AC-01", "SPEC-037")` and `@traces("REQ-037", "AC-02", "SPEC-037")`.
- In `tests/test_stage_runner.py`, add `test_multi_artifact_stage_review_pass_and_second_artifact_rejection` with `@traces("REQ-037", "AC-01", "SPEC-037")` and `@traces("REQ-037", "AC-03", "SPEC-037")`.
