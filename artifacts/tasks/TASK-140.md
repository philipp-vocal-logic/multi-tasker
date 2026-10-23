---
id: TASK-140
title: Harden Multi-Language Checkers, Layer Glob Matching, and Greenfield Mypy
type: implementation
status: ready
traces_to:
- REQ-053
- SPEC-053
depends_on:
- TASK-139
required_files:
- tests/test_multi_language_greenfield_hardening.py
- src/multi_tasker/checkers/language_support.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
write_files:
- src/multi_tasker/checkers/language_parser.py
- src/multi_tasker/checkers/language_support.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_greenfield_hardening.py -k "not review_prompt"
---
## Objective
Extract `language_parser.py` from `language_support.py` and harden `architecture_checker.py` and `clean_code_checker.py` for greenfield multi-language repositories.

## Scoped Instructions
- Create `src/multi_tasker/checkers/language_parser.py` masking C and Rust comments/literals while preserving line numbers, parsing generic/`where`/`[T; N]` signatures, and extracting multi-word C variable declarations.
- Update `language_support.py` to use `language_parser.py`, resolve relative C `#include` and Rust `super`/`self` imports, and isolate `@traces` blocks per test function.
- Update `architecture_checker.py` to prevent single-star globs from crossing `/` and ignore self-edges, and update `clean_code_checker.py` (`_run_mypy`) for greenfield `MYPYPATH`, `--ignore-missing-imports` on `tests/`, and `: error:` extraction.
