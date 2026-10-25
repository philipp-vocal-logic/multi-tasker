---
id: TASK-147
title: Add TestContract for Linear-Time Rust Function Signature Regex
type: test_contract
status: done
traces_to:
- REQ-056
- SPEC-056
depends_on: []
required_files:
- tests/test_multi_language_greenfield_hardening.py
write_files:
- tests/test_multi_language_greenfield_hardening.py
verification_cmd: python3 -m py_compile tests/test_multi_language_greenfield_hardening.py
---
## Objective
Add `@traces("REQ-056", "AC-01", "SPEC-056")` and pathological bracket-repetition assertions in `tests/test_multi_language_greenfield_hardening.py`.

## Scoped Instructions
- Tag `test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing` with `@traces("REQ-056", "AC-01", "SPEC-056")` and verify `RUST_FN_REGEX` does not backtrack exponentially on `"fn A()->" + "[]" * 40` and rejects overlapping `"[^{;]+"` inside `RUST_FN_REGEX.pattern`.
