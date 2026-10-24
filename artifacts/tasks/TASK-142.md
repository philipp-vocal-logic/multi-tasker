---
id: TASK-142
title: Add TestContracts for Line-1 Traces, String-Return Non-Stubs, and Rust Tuple/Group
  Parsing
type: test_contract
status: done
traces_to:
- REQ-054
- SPEC-054
depends_on: []
required_files:
- tests/test_multi_language_greenfield_hardening.py
write_files:
- tests/test_multi_language_greenfield_hardening.py
verification_cmd: python3 -m py_compile tests/test_multi_language_greenfield_hardening.py
---
## Objective
Extend `tests/test_multi_language_greenfield_hardening.py` with `@traces("REQ-054", ...)` assertions for line-1 `@traces`, string-literal return bodies, Rust tuple `let (x, y)`, and grouped `use` imports.

## Scoped Instructions
- Decorate `test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing` with `@traces("REQ-054", "AC-01", "SPEC-054")` and `@traces("REQ-054", "AC-02", "SPEC-054")` and assert line-1 `@traces` extraction, string-return non-stub functions, Rust tuple `let (x, y)`, and grouped `use` imports.
