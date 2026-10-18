---
id: TASK-055
title: Implement Non-Blocking 400-Line Refactoring Target Collector and Planning Prompt Warnings
type: implementation
status: planned
traces_to:
- REQ-018
- SPEC-018
depends_on:
- TASK-054
required_files:
- tests/test_transitions_and_execution.py
- src/checkers/limits_checker.py
- src/orchestrator/prompt_builder.py
write_files:
- src/checkers/limits_checker.py
- src/orchestrator/prompt_builder.py
verification_cmd: pytest -q tests/test_transitions_and_execution.py tests/test_orchestrator.py
---
## Objective
Implement `collect_refactoring_targets` in `src/checkers/limits_checker.py` and surface non-blocking `LIMIT_REFACTOR_HINT` warnings in `specification-agent` and `planner-agent` prompts in `src/orchestrator/prompt_builder.py`.

## Scoped Instructions
In `src/checkers/limits_checker.py`, add `collect_refactoring_targets(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]` that emits `LIMIT_REFACTOR_HINT` `Findings` for Python files whose line count exceeds `refactor_target_file_lines` (`400`) up to `max_file_lines` (`500`), while `check_limits` continues to only fail above `max_file_lines`. In `src/orchestrator/prompt_builder.py`, update `_render_code_and_glossary_section` to append `- **Refactoring Targets (Warning)**: ...` for `specification-agent` and `planner-agent` when `collect_refactoring_targets(repository_root)` returns warnings.
