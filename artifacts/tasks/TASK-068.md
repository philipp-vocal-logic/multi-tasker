---
id: TASK-068
title: Add TestContract for Ephemeral Python and Pytest Cache Filtering
type: test_contract
status: planned
traces_to:
  - REQ-024
  - SPEC-024
depends_on: []
required_files:
  - artifacts/requirements/REQ-024.md
  - artifacts/specifications/SPEC-024.md
write_files:
  - tests/test_checkers.py
verification_cmd: python3 -m py_compile tests/test_checkers.py
---
## Objective
Add `test_gitignore_scaffolding_and_changed_files_exclude_python_caches` decorated with `@traces("REQ-024", "AC-01", "SPEC-024")` in `tests/test_checkers.py`.

## Scoped Instructions
Verify `initialize_repository` writes `__pycache__/`, `*.py[cod]`, and `.pytest_cache/` into `.gitignore`, and `get_git_changed_files` excludes `.pyc`, `__pycache__/`, and `.pytest_cache/` files even if `.gitignore` is absent.
