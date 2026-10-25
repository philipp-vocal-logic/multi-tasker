---
id: TASK-149
title: Add TestContract for Bidirectional Dependency Parity in test_architecture_checker
type: test_contract
status: done
traces_to:
- REQ-057
- SPEC-057
depends_on: []
required_files:
- tests/test_architecture_checker.py
- pyproject.toml
- policy/code_architecture.yaml
write_files:
- tests/test_architecture_checker.py
verification_cmd: python3 -m py_compile tests/test_architecture_checker.py
---
## Objective
Add `test_repository_dependency_single_source_of_truth` decorated with `@traces("REQ-057", "AC-01", "SPEC-057")` in `tests/test_architecture_checker.py`.

## Scoped Instructions
- Parse `pyproject.toml` via `tomllib` and resolve import module names via `importlib.metadata.packages_distributions()`.
- Verify `src/**` third-party imports equal `pyproject.toml` runtime dependencies, `dev` dependencies are all used by `tests/**`, linters, or type stubs, and `policy/code_architecture.yaml` and `DEFAULT_PYTHON_ARCHITECTURE` match `["yaml", "pytest", "multi_tasker"]`.
