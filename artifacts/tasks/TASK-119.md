---
id: TASK-119
title: Add TestContracts for Worktree Src PYTHONPATH Precedence and Identical Review
  Retry
type: test_contract
status: done
traces_to:
- REQ-047
- SPEC-047
depends_on: []
required_files:
- artifacts/requirements/REQ-047.md
- artifacts/specifications/SPEC-047.md
- tests/test_pipeline_combinations.py
write_files:
- tests/test_pipeline_combinations.py
verification_cmd: python3 -m py_compile tests/test_pipeline_combinations.py
---
## Objective
Update `tests/test_pipeline_combinations.py` (staying at or below 400 lines) to test `REQ-047:AC-01`, `REQ-047:AC-02`, and `REQ-047:AC-03`, including byte-identical Cycle-2 `REV-001.md` writes in `_T_REV_F2` and `test_worktree_pythonpath_precedence_and_identical_review_retry`.

## Scoped Instructions
- Change `_T_REV_F2` in `tests/test_pipeline_combinations.py` back to `{_REV_PATH: _rev_md("fail")}` so Scenario 4 tests byte-identical Cycle-2 `REV-001.md` normalization (`REQ-047:AC-02`).
- Add `test_worktree_pythonpath_precedence_and_identical_review_retry` decorated with `@traces("REQ-047", "AC-01", "SPEC-047")`, `@traces("REQ-047", "AC-02", "SPEC-047")`, and `@traces("REQ-047", "AC-03", "SPEC-047")` while keeping `tests/test_pipeline_combinations.py` <= 400 lines.
