---
id: SPEC-016
title: Configurable Library Deployment and External Repository Initialization Specification
status: approved
traces_to:
- REQ-016
covers_criteria:
- REQ-016:AC-01
- REQ-016:AC-02
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  - tests/test_traceability_and_cli.py
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/checkers/architecture_checker.py
---
## Design Overview
Expose `multi_tasker` (`multi_tasker.domain`, `multi_tasker.checkers`, `multi_tasker.orchestrator`, `multi_tasker.cli`, `multi_tasker.policy_templates`) in `pyproject.toml` and allow `"multi_tasker"` in `policy/architecture.yaml`. Update `initialize_repository` in `src/multi_tasker/orchestrator/lifecycle.py` to copy missing default `policy/*.yaml` files from bundled templates and ensure `.gitignore` contains `.worktrees/`, `.report/`, and `.mt_prompt.md`. Update `src/multi_tasker/checkers/architecture_checker.py` to derive scanned folders and internal package prefixes from `policy/architecture.yaml`. Prepend `worktree_path` to `PYTHONPATH` in `src/multi_tasker/orchestrator/prompt_builder.py` and `src/multi_tasker/orchestrator/stage_runner.py`.

## Public Interfaces
- `pyproject.toml`:
  - `tool.setuptools.package-dir`: maps `multi_tasker` to `src` and `multi_tasker.policy_templates` to `policy`
- `policy/architecture.yaml`:
  - `allowed_third_party_packages` includes `"multi_tasker"`
- `src/multi_tasker/orchestrator/lifecycle.py`:
  - `_scaffold_default_policies_and_gitignore(repository_root: Path) -> None`
  - `initialize_repository(repository_root: Path) -> list[Finding]`
- `src/multi_tasker/checkers/architecture_checker.py`:
  - `_extract_layer_folders(layers: list[dict[str, Any]]) -> tuple[str, ...]`
  - `_extract_internal_packages(layers: list[dict[str, Any]]) -> set[str]`
- `src/multi_tasker/orchestrator/prompt_builder.py` & `src/multi_tasker/orchestrator/stage_runner.py`:
  - `PYTHONPATH` formatted as `f"{worktree_path}{os.pathsep}{mt_root}"`

## Test Contract Mapping
- `REQ-016:AC-01` $\rightarrow$ `tests/test_interaction_logging.py::test_initialize_scaffolds_default_policies_and_gitignore`
- `REQ-016:AC-02` $\rightarrow$ `tests/test_interaction_logging.py::test_architecture_custom_package_and_worktree_pythonpath`
