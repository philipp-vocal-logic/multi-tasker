---
id: TASK-118
title: Fix Scenario Commit Helper and Cycle-2 Fail Review ID in E2E Test Suite
type: test_contract
status: done
traces_to:
- REQ-046
- SPEC-046
depends_on:
- TASK-117
required_files:
- tests/test_pipeline_combinations.py
write_files:
- tests/test_pipeline_combinations.py
verification_cmd: pytest -q tests/test_task_runner.py -k test_modular_refactoring_and_file_size_ceilings
---
## Objective
Update `_configure_scenario_repository` in `tests/test_pipeline_combinations.py` to use `commit_traceable_change` (handling no-op gate changes cleanly) and write `REV-002.md` in `_T_REV_F2`.

## Scoped Instructions
- Replace `_git_commit_all` with `commit_traceable_change` in `_configure_scenario_repository`.
- Have `_T_REV_F2` write `artifacts/reviews/REV-002.md` (`id: REV-002`) so Cycle 2 review rejection produces a non-empty worktree diff.
