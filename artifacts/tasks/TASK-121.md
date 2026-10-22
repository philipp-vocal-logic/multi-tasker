---
id: TASK-121
title: Order Empty Stage Diff Assertion Before Untracked Module Creation in TestContract
type: test_contract
status: ready
traces_to:
  - REQ-047
  - SPEC-047
depends_on:
  - TASK-119
required_files:
  - artifacts/requirements/REQ-047.md
  - artifacts/specifications/SPEC-047.md
  - tests/test_pipeline_combinations.py
write_files:
  - tests/test_pipeline_combinations.py
verification_cmd: python3 -m py_compile tests/test_pipeline_combinations.py
---
## Objective
Assert empty stage diff detection (`REQ-047:AC-03`) in `test_worktree_pythonpath_precedence_and_identical_review_retry` on a clean Git working tree before creating the untracked `src/domain/mod.py` fixture file for `REQ-047:AC-01`.

## Scoped Instructions
- Move the `before_empty = stage_runner._snapshot_artifacts(tmp_path)` and `assert stage_runner._detect_stage_changes(tmp_path, before_empty, "INT-001") == []` assertions ahead of `(tmp_path / "src/domain").mkdir(...)` in `tests/test_pipeline_combinations.py`.
