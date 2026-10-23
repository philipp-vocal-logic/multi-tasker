---
id: SPEC-053
title: Greenfield Multi-Language Checker Sanitization, Layer Resolution, Mypy, and
  Orchestrator Hardening
status: approved
traces_to:
- REQ-053
covers_criteria:
- REQ-053:AC-01
- REQ-053:AC-02
- REQ-053:AC-03
decisions: []
target_files:
  tests:
  - tests/test_multi_language_greenfield_hardening.py
  implementation:
  - src/multi_tasker/checkers/language_parser.py
  - src/multi_tasker/checkers/language_support.py
  - src/multi_tasker/checkers/architecture_checker.py
  - src/multi_tasker/checkers/clean_code_checker.py
  - src/multi_tasker/orchestrator/language_presets.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/lineage.py
  - src/multi_tasker/orchestrator/worktree.py
---
## Design Overview
Harden multi-language greenfield execution across checkers and orchestrator:
- Extract `src/multi_tasker/checkers/language_parser.py` from `language_support.py` to mask C and Rust comments and string/character literals while preserving line numbers, parse generic/`where`/`[T; N]` signatures, extract multi-word C variable declarations, resolve local C `#include` and Rust `super`/`self` imports, and isolate `@traces` blocks per test function.
- Update `architecture_checker.py` and `lifecycle.py` so single-star layer globs (`src/*.*`) do not shadow subdirectory layers (`src/services/**`, `src/cli/**`) and self-edges (`mod -> mod`) are ignored.
- Update `clean_code_checker.py` (`_run_mypy`) to avoid duplicate module paths, include `multi_tasker`'s `src` path, pass `--ignore-missing-imports` on `tests/`-only checks, and report `: error:` lines.
- Update `language_presets.py`, `prompt_builder.py`, `prompt_context.py`, `lineage.py`, and `worktree.py` for review scope, `.report` creation, and non-Python documentation/prompts.

## Public Interfaces
```python
def mask_string_and_character_literals(source_code: str) -> str: ...

def mask_comments_and_literals(source_code: str) -> str: ...

def extract_c_and_rust_functions(
    source_code: str, relative_path: str
) -> list[ParsedFunction]: ...

def extract_declared_variables(
    masked_code: str, is_rust: bool
) -> list[tuple[str, int]]: ...
```

## Test Contract Mapping
- `REQ-053:AC-01` -> `tests/test_multi_language_greenfield_hardening.py::test_layer_globs_c_self_and_relative_includes_and_greenfield_mypy`
- `REQ-053:AC-02` -> `tests/test_multi_language_greenfield_hardening.py::test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing`
- `REQ-053:AC-03` -> `tests/test_multi_language_greenfield_hardening.py::test_review_prompt_scope_worktree_report_dir_and_non_python_documentation`
