---
id: TASK-060
title: Add TestContract for Real-Git Pipeline Commits, Verification PYTHONPATH, and
  REV Traceability
type: test_contract
status: done
traces_to:
- REQ-021
- SPEC-021
depends_on: []
required_files:
- tests/test_stage_runner.py
write_files:
- tests/test_stage_runner.py
verification_cmd: python3 -m py_compile tests/test_stage_runner.py
---
## Objective
Add `test_real_git_pipeline_commits_verification_pythonpath_and_rev_traceability` in `tests/test_stage_runner.py` with `@traces("REQ-021", "AC-01", "SPEC-021")` and `@traces("REQ-021", "AC-02", "SPEC-021")`.

## Scoped Instructions
- Initialize a real Git repository in `tmp_path`, commit baseline policies and `INT-001`, and execute `mt run --pipeline` through `REQ-001`, `SPEC-001`, `REV-*`, `TASK-001` (`test_contract`), and `TASK-002` (`implementation`) with `require_spec_target_files_covered_by_tasks` enabled.
- Verify `resolve_task_execution` resolves `default_environment`, `verification_cmd` imports from `worktree_path` and `multi-tasker` via `PYTHONPATH`, and `mt check all` exits `0` on the resulting Git commit history.
