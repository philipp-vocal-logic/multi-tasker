---
id: SPEC-024
title: Ephemeral Python and Pytest Cache Ignore Specification
status: approved
traces_to:
- REQ-024
covers_criteria:
- REQ-024:AC-01
decisions: []
target_files:
  tests:
  - tests/test_checkers.py
  implementation:
  - src/orchestrator/lifecycle.py
  - src/checkers/common.py
---
## Design Overview
Expand `DEFAULT_GITIGNORE_ENTRIES` in `src/orchestrator/lifecycle.py` with `"__pycache__/"`, `"*.py[cod]"`, and `".pytest_cache/"`, and add a path filter in `get_git_changed_files` in `src/checkers/common.py` so untracked or modified cache files under `__pycache__/` or `.pytest_cache/` and `.pyc`/`.pyo`/`.pyd` files are never returned as changed repository paths.

## Public Interfaces
- `get_git_changed_files(repository_root: Path) -> list[str]`
- `initialize_repository(repository_root: Path) -> list[Finding]`

## Test Contract Mapping
- `REQ-024:AC-01` -> `tests/test_checkers.py::test_gitignore_scaffolding_and_changed_files_exclude_python_caches`
