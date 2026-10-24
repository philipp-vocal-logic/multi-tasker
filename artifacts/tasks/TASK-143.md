---
id: TASK-143
title: Implement Line-1 Trace Preamble Fix, String-Return Non-Stubs, and Rust Tuple/Group
  Parsing
type: implementation
status: done
traces_to:
- REQ-054
- SPEC-054
depends_on:
- TASK-142
required_files:
- tests/test_multi_language_greenfield_hardening.py
- src/multi_tasker/checkers/language_parser.py
- src/multi_tasker/checkers/language_support.py
write_files:
- src/multi_tasker/checkers/language_parser.py
- src/multi_tasker/checkers/language_support.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_greenfield_hardening.py
---
## Objective
Update `language_parser.py` and `language_support.py` to preserve line-1 `@traces`, keep string literals in `body_text`, and parse Rust tuple `let` and grouped `use`.

## Scoped Instructions
- Add `mask_comments_only` in `language_parser.py`, slice `ParsedFunction.body_text` from `mask_comments_only(source_code)`, and extract Rust tuple `let (a, b)` identifiers in `extract_declared_variables`.
- Update `_extract_preceding_annotation_block` in `language_support.py` to use `max(-1, min_line - 2)` and expand grouped `use prefix::{a, b}` in `extract_non_python_imports`.
