---
id: SPEC-051
title: Policy-Driven Language Extensions, Ephemeral Globs, Forbidden Calls, and Test
  Commands Specification
status: approved
traces_to:
- REQ-051
covers_criteria:
- REQ-051:AC-01
- REQ-051:AC-02
- REQ-051:AC-03
decisions: []
target_files:
  tests:
  - tests/test_clean_code_checker.py
  - tests/test_lifecycle.py
  - tests/test_orchestrator.py
  - tests/test_prompt_builder.py
  implementation:
  - src/multi_tasker/checkers/common.py
  - src/multi_tasker/checkers/architecture_checker.py
  - src/multi_tasker/checkers/clean_code_checker.py
  - src/multi_tasker/checkers/limits_checker.py
  - src/multi_tasker/checkers/glossary_checker.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/lineage.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/prompt_builder.py
---
## Design Overview
Move language and build constants out of `src/**` into `policy/*.yaml`:
- Read `clean_repo_invariants.ignored_ephemeral_globs` from `policy/agent_execution.yaml` via `load_ephemeral_globs(repository_root)` in `common.py` for `get_git_changed_files` and `.gitignore` scaffolding in `lifecycle.py`.
- Read `language` and `source_extensions` from `policy/code_quality.yaml` via `load_source_extensions(repository_root)` in `common.py` across all five source checkers, and enforce `ast_rules.forbidden_calls_in_src` in `clean_code_checker.py`.
- Read `test_file_glob`, `test_contract_verification_cmd`, and `implementation_verification_cmd` from `policy/traceability.yaml` in `code_and_git_traceability.py`, `lineage.py`, `prompt_context.py`, and `prompt_builder.py`.

## Public Interfaces
```python
def load_ephemeral_globs(repository_root: Path) -> tuple[str, ...]: ...

def load_source_extensions(repository_root: Path) -> set[str]: ...

def render_decomposition_contract(
    agent_role: str,
    next_id: str | None,
    repository_root: Path | None = None,
) -> list[str]: ...
```

## Test Contract Mapping
- `REQ-051:AC-01` -> `tests/test_lifecycle.py::test_initialize_and_intent_creation_with_git`, `tests/test_orchestrator.py::test_all_policy_yaml_keys_are_enforced_and_read`
- `REQ-051:AC-02` -> `tests/test_clean_code_checker.py::test_clean_code_checker_violation_branches`, `tests/test_clean_code_checker.py::test_output_contract_mypy_and_toggle_sensitivity`
- `REQ-051:AC-03` -> `tests/test_prompt_builder.py::test_planner_single_concern_decomposition_contract`, `tests/test_orchestrator.py::test_all_policy_yaml_keys_are_enforced_and_read`
