---
id: TASK-047
title: Add TestContracts for Policy Scaffolding, Custom Architecture Packages, and Worktree PYTHONPATH
type: test_contract
status: planned
traces_to:
- REQ-016
- SPEC-016
depends_on: []
required_files:
- tests/test_lifecycle.py
- tests/test_traceability_and_cli.py
write_files:
- tests/test_lifecycle.py
- tests/test_traceability_and_cli.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_orchestrator.py
---
## Objective
Add `@traces("REQ-016", "AC-01", "SPEC-016")` and `@traces("REQ-016", "AC-02", "SPEC-016")` test contracts to `tests/test_lifecycle.py` and `tests/test_traceability_and_cli.py`.

## Scoped Instructions
Add `test_initialize_scaffolds_default_policies_and_gitignore` (`@traces("REQ-016", "AC-01", "SPEC-016")`) to `tests/test_lifecycle.py` verifying `mt initialize` populates missing `policy/*.yaml` files (including `"multi_tasker"` in `architecture.yaml`) and `.gitignore` entries without overwriting existing files. Add `test_architecture_custom_package_and_worktree_pythonpath` (`@traces("REQ-016", "AC-02", "SPEC-016")`) to `tests/test_traceability_and_cli.py` verifying `check_architecture` enforces custom layer folders and internal package prefixes and `prepare_worker_invocation` places `worktree_path` first in `PYTHONPATH`.
