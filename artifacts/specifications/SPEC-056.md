---
id: SPEC-056
title: Disjoint-Branch Rust and C Signature Regular Expression Specification
status: approved
traces_to:
- REQ-056
covers_criteria:
- REQ-056:AC-01
decisions: []
target_files:
  tests:
  - tests/test_multi_language_greenfield_hardening.py
  implementation:
  - src/multi_tasker/checkers/language_parser.py
---
## Design Overview
Replace the overlapping `(?:\[[^\]]*\]|[^{;])+` alternation in `RUST_FN_REGEX` with `(?:\[[^\]{}]*\]|[^{;\[])*\{` so `[` and non-`[` characters take strictly disjoint branches, and tighten `C_FN_REGEX` and `C_VAR_DECL_REGEX` quantifiers.

## Public Interfaces
```python
RUST_FN_REGEX: re.Pattern[str]
C_FN_REGEX: re.Pattern[str]
C_VAR_DECL_REGEX: re.Pattern[str]
```

## Test Contract Mapping
- `REQ-056:AC-01` -> `tests/test_multi_language_greenfield_hardening.py::test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing`
