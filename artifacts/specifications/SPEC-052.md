---
id: SPEC-052
title: Multi-Language Checkers, Presets, Prompt Contracts, and Pipeline Execution
  Specification
status: approved
traces_to:
- REQ-052
covers_criteria:
- REQ-052:AC-01
- REQ-052:AC-02
- REQ-052:AC-03
decisions: []
target_files:
  tests:
  - tests/test_multi_language_pipeline.py
  implementation:
  - src/multi_tasker/checkers/language_support.py
  - src/multi_tasker/checkers/architecture_checker.py
  - src/multi_tasker/checkers/clean_code_checker.py
  - src/multi_tasker/checkers/limits_checker.py
  - src/multi_tasker/checkers/glossary_checker.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
  - src/multi_tasker/orchestrator/language_presets.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/lineage.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
Extend `multi-tasker` to validate and execute ANSI C (`ansi-c`) and Rust (`rust`) projects alongside Python:
- Add `src/multi_tasker/checkers/language_support.py` to parse `.c`, `.h`, and `.rs` files for comments, doc comments, function spans/arguments/stubs, identifiers, forbidden calls, `#include`/`use`/`mod` imports, and `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` annotations.
- Integrate `language_support` into `architecture_checker.py`, `clean_code_checker.py`, `limits_checker.py`, `glossary_checker.py`, `code_and_git_traceability.py`, and `lineage.py`.
- Add `src/multi_tasker/orchestrator/language_presets.py` and update `lifecycle.py`, `prompt_builder.py`, and `prompt_context.py` so `mt initialize --preset <python|ansi-c|rust|multi-tasker>` and `mt prompt` emit language-specific policies, code fences, and `TestContract` templates.

## Public Interfaces
```python
def check_non_python_clean_code(
    source_code: str, relative_path: str, ast_configuration: dict[str, Any]
) -> list[Finding]: ...

def check_non_python_file_limits(
    source_code: str, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]: ...

def extract_non_python_imports(
    source_code: str, relative_path: str
) -> list[tuple[str, int]]: ...

def extract_non_python_test_functions(
    source_code: str, decorator_name: str, argument_count: int
) -> list[tuple[str, int, list[tuple[str, str, str]]]]: ...

def apply_language_preset_policies(
    repository_root: Path, preset: str
) -> None: ...
```

## Test Contract Mapping
- `REQ-052:AC-01` -> `tests/test_multi_language_pipeline.py::test_ansi_c_and_rust_checkers_enforce_limits_clean_code_glossary_and_architecture`
- `REQ-052:AC-02` -> `tests/test_multi_language_pipeline.py::test_initialize_presets_and_prompt_synthesis_for_ansi_c_and_rust`
- `REQ-052:AC-03` -> `tests/test_multi_language_pipeline.py::test_end_to_end_pipeline_execution_across_python_ansi_c_and_rust`
