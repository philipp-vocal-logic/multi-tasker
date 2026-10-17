---
id: TASK-052
title: Add TestContract for External Project AGENTS.md Bootstrapping and Policy Guide Scaffolding
type: test_contract
status: planned
traces_to:
- REQ-017
- SPEC-017
depends_on: []
required_files:
- tests/test_interaction_logging.py
write_files:
- tests/test_interaction_logging.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Update `test_initialize_scaffolds_default_policies_and_gitignore` in `tests/test_interaction_logging.py` with `@traces("REQ-017", "AC-01", "SPEC-017")` assertions for external `AGENTS.md` scaffolding and non-overwrite behavior.

## Scoped Instructions
Add `@traces("REQ-017", "AC-01", "SPEC-017")` to `test_initialize_scaffolds_default_policies_and_gitignore` in `tests/test_interaction_logging.py` and assert that `mt initialize` generates `AGENTS.md` containing `policy/architecture.yaml`, `PERM_POLICY_MODIFIED`, and `from multi_tasker.domain.models import traces`, and does not overwrite an existing `AGENTS.md`.
