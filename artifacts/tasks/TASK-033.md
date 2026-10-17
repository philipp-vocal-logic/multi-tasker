---
id: TASK-033
title: Create TestContract for Configurable Orchestrator Context Delivery Mode
type: test_contract
status: planned
traces_to:
- REQ-012
- SPEC-012
depends_on: []
required_files: []
write_files:
- tests/test_interaction_logging.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Add `TestContract` coverage in `tests/test_interaction_logging.py` for `REQ-012:AC-01` and `REQ-012:AC-02`.

## Scoped Instructions
Add `test_context_mode_policy_validation_and_precedence` (`@traces("REQ-012", "AC-01", "SPEC-012")`) and `test_prompt_and_worktree_run_context_modes` (`@traces("REQ-012", "AC-02", "SPEC-012")`) to `tests/test_interaction_logging.py` verifying `default_context_mode` validation in `check_permissions`, `CLI > Task > Policy` resolution in `resolve_context_mode`, `inline` vs `paths` synthesis in `mt prompt`, and `MT_CONTEXT_MODE` in `mt run`.
