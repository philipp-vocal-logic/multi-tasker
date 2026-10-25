---
id: SPEC-057
title: Bidirectional Dependency Parity and Allowlist Cleanup Specification
status: approved
traces_to:
- REQ-057
covers_criteria:
- REQ-057:AC-01
decisions: []
target_files:
  tests:
  - tests/test_architecture_checker.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Remove unused `"jsonschema"` from `allowed_third_party_packages` in `policy/code_architecture.yaml` and `DEFAULT_PYTHON_ARCHITECTURE` in `lifecycle.py`, and verify bidirectional dependency equivalence across `pyproject.toml`, `policy/code_architecture.yaml`, and repository AST imports using stdlib `tomllib` and `importlib.metadata`.

## Public Interfaces
```python
DEFAULT_PYTHON_ARCHITECTURE: dict[str, object]
```

## Test Contract Mapping
- `REQ-057:AC-01` -> `tests/test_architecture_checker.py::test_repository_dependency_single_source_of_truth`
