---
id: TASK-137
title: Implement Multi-Language Support Across Checkers for ANSI C and Rust
type: implementation
status: ready
traces_to:
- REQ-052
- SPEC-052
depends_on:
- TASK-136
required_files:
- tests/test_multi_language_pipeline.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/glossary_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
write_files:
- src/multi_tasker/checkers/language_support.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/glossary_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_pipeline.py -k checkers
---
## Objective
Add `src/multi_tasker/checkers/language_support.py` and integrate `.c`, `.h`, and `.rs` analysis into all five source code checkers.

## Scoped Instructions
- Create `src/multi_tasker/checkers/language_support.py` parsing C and Rust comments, doc comments, function spans/arguments/stubs, identifiers, forbidden calls, `#include`/`use`/`mod` imports, and `@traces` test annotations.
- Update `architecture_checker.py`, `clean_code_checker.py`, `limits_checker.py`, `glossary_checker.py`, and `code_and_git_traceability.py` to dispatch non-Python source and test files (`.c`, `.h`, `.rs`) through `language_support.py`.
