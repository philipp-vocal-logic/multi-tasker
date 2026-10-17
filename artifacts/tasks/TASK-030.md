---
id: TASK-030
title: Create TestContract for CLI Invocation and Worktree Interaction Logging
type: test_contract
status: ready
traces_to:
- REQ-011
- SPEC-011
depends_on: []
required_files: []
write_files:
- tests/test_interaction_logging.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Add `TestContract` coverage in `tests/test_interaction_logging.py` for `REQ-011:AC-01` and `REQ-011:AC-02`.

## Scoped Instructions
Create `tests/test_interaction_logging.py` with `test_cli_invocations_logged_to_events_and_task_logs` (`@traces("REQ-011", "AC-01", "SPEC-011")`) and `test_worktree_task_execution_and_merge_gate_logs_merged` (`@traces("REQ-011", "AC-02", "SPEC-011")`) verifying CLI invocation logs, `Worktree` execution logs, `MergeGate` logs, and separation from `Specification` generation.
