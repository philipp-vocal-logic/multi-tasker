---
id: TASK-148
title: Implement Disjoint-Branch Rust and C Regular Expressions in language_parser
type: implementation
status: ready
traces_to:
  - REQ-056
  - SPEC-056
depends_on:
  - TASK-147
required_files:
  - tests/test_multi_language_greenfield_hardening.py
  - src/multi_tasker/checkers/language_parser.py
write_files:
  - src/multi_tasker/checkers/language_parser.py
verification_cmd: pytest -o pythonpath=src -q tests/test_multi_language_greenfield_hardening.py
---
## Objective
Eliminate overlapping regex quantifiers in `RUST_FN_REGEX`, `C_FN_REGEX`, and `C_VAR_DECL_REGEX` in `src/multi_tasker/checkers/language_parser.py`.

## Scoped Instructions
- Update `RUST_FN_REGEX` in `src/multi_tasker/checkers/language_parser.py` to use `(?:\[[^\]{}]*\]|[^{;\[])*\{` and tighten `C_FN_REGEX` and `C_VAR_DECL_REGEX` whitespace/pointer quantifiers.
