---
id: SPEC-054
title: Line-1 Trace Preamble, String-Return Body Extraction, and Rust Tuple/Group
  Parser Specification
status: approved
traces_to:
- REQ-054
covers_criteria:
- REQ-054:AC-01
- REQ-054:AC-02
decisions: []
target_files:
  tests:
  - tests/test_multi_language_greenfield_hardening.py
  implementation:
  - src/multi_tasker/checkers/language_parser.py
  - src/multi_tasker/checkers/language_support.py
---
## Design Overview
Refine `language_parser.py` and `language_support.py` for remaining greenfield probe edge cases:
- Fix `_extract_preceding_annotation_block` range stop index to `max(-1, min_line - 2)` so 1-based `min_line = 1` includes 0-based line index `0`.
- Slice `ParsedFunction.body_text` from comment-masked source (preserving string literals) so functions returning `"}"` or string literals are not flagged as `CODE_STUB_FUNCTION`.
- Support Rust tuple destructuring `let (x, y) = ...` in `extract_declared_variables` and grouped `use prefix::{a, b}` in `extract_non_python_imports`.

## Public Interfaces
```python
def mask_comments_only(source_code: str) -> str: ...
```

## Test Contract Mapping
- `REQ-054:AC-01` -> `tests/test_multi_language_greenfield_hardening.py::test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing`
- `REQ-054:AC-02` -> `tests/test_multi_language_greenfield_hardening.py::test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing`
