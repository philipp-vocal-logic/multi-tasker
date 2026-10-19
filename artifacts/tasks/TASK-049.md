---
id: TASK-049
title: Implement Configurable Layer Folders and Internal Package Prefixes in Architecture
  Checker
type: implementation
status: done
traces_to:
- REQ-016
- SPEC-016
depends_on:
- TASK-047
- TASK-048
required_files:
- tests/test_traceability_and_cli.py
- src/multi_tasker/checkers/architecture_checker.py
write_files:
- src/multi_tasker/checkers/architecture_checker.py
verification_cmd: pytest -q tests/test_traceability_and_cli.py tests/test_lifecycle.py
  tests/test_orchestrator.py
---
## Objective
Derive scanned layer directories and internal package prefixes dynamically from `policy/architecture.yaml` in `src/multi_tasker/checkers/architecture_checker.py`.

## Scoped Instructions
Add `_extract_layer_folders` and `_extract_internal_packages` in `src/multi_tasker/checkers/architecture_checker.py` and wire them into `_check_single_import`, `_check_file_imports`, and `check_architecture` so custom package prefixes and layer folders are checked for layer boundaries and circular imports.
