---
id: TASK-036
title: Create TestContract for Per-Agent Worktree Execution and Role Models
type: test_contract
status: done
traces_to:
- REQ-013
- SPEC-013
depends_on: []
required_files: []
write_files:
- tests/test_stage_runner.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Add `TestContract` coverage in `tests/test_stage_runner.py` for `REQ-013:AC-01` and `REQ-013:AC-02`.

## Scoped Instructions
Create `tests/test_stage_runner.py` with `test_per_agent_model_precedence_and_policy_validation` (`@traces("REQ-013", "AC-01", "SPEC-013")`) and `test_configurable_worktree_stage_execution_and_toggle` (`@traces("REQ-013", "AC-02", "SPEC-013")`) verifying `gemini-4-argon` role defaults, 4-tier model resolution, `check_permissions` validation, and `mt run --agent <role> --target <id>` execution and toggles.
