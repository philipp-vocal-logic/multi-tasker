---
id: TASK-139
title: Add Greenfield Multi-Language Hardening TestContracts
type: test_contract
status: done
traces_to:
- REQ-053
- SPEC-053
depends_on: []
required_files:
- tests/test_multi_language_pipeline.py
write_files:
- tests/test_multi_language_greenfield_hardening.py
verification_cmd: python3 -m py_compile tests/test_multi_language_greenfield_hardening.py
---
## Objective
Create `tests/test_multi_language_greenfield_hardening.py` with `@traces("REQ-053", ...)` TestContracts covering `REQ-053:AC-01` through `REQ-053:AC-03`.

## Scoped Instructions
- Add `test_layer_globs_c_self_and_relative_includes_and_greenfield_mypy` (`@traces("REQ-053", "AC-01", "SPEC-053")`) verifying subdirectory layer matching, C self/relative includes, and greenfield `mypy` execution.
- Add `test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing` (`@traces("REQ-053", "AC-02", "SPEC-053")`) verifying comment/string sanitization, generics/`where`/`[T; N]` signatures, multi-word C variables, `use super::*`, and isolated `@traces` blocks.
- Add `test_review_prompt_scope_worktree_report_dir_and_non_python_documentation` (`@traces("REQ-053", "AC-03", "SPEC-053")`) verifying `review-agent` prompt scope on `TASK`, `.report` worktree creation, and non-Python `mt documentation`.
