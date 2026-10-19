---
id: SPEC-018
title: Non-Blocking Refactoring Target Warnings and 500-Line Hard Limit Specification
status: approved
traces_to:
- REQ-018
covers_criteria:
- REQ-018:AC-01
- REQ-018:AC-02
decisions: []
target_files:
  tests:
  - tests/test_transitions_and_execution.py
  implementation:
  - src/multi_tasker/checkers/limits_checker.py
  - src/multi_tasker/orchestrator/prompt_builder.py
---
## Design Overview
Configure `refactor_target_file_lines: 400` alongside `max_file_lines: 500` in `policy/limits.yaml`. Add `collect_refactoring_targets(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]` in `src/multi_tasker/checkers/limits_checker.py` to emit non-blocking `LIMIT_REFACTOR_HINT` `Findings` for Python files whose line count exceeds `refactor_target_file_lines` (`400`) while `check_limits` continues to only fail above `max_file_lines` (`500`). Update `src/multi_tasker/orchestrator/prompt_builder.py` so `specification-agent` and `planner-agent` prompts include a `Refactoring Targets` warning block when any repository module exceeds `refactor_target_file_lines`. Update `tests/test_transitions_and_execution.py` to enforce `max_file_lines` (`500`) from `policy/limits.yaml` instead of `360` and verify non-blocking `400`-line refactoring warnings.

## Public Interfaces
- `src/multi_tasker/checkers/limits_checker.py`:
  - `collect_refactoring_targets(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]`
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `_render_code_and_glossary_section(repository_root: Path, agent_role: str, context_mode: str = "inline") -> list[str]` appends `- **Refactoring Targets (Warning)**: ...` for `specification-agent` and `planner-agent` when `collect_refactoring_targets(repository_root)` is non-empty.

## Test Contract Mapping
- `REQ-018:AC-01` $\rightarrow$ `tests/test_transitions_and_execution.py::test_modular_refactoring_and_file_size_ceilings`
- `REQ-018:AC-02` $\rightarrow$ `tests/test_transitions_and_execution.py::test_modular_refactoring_and_file_size_ceilings`
