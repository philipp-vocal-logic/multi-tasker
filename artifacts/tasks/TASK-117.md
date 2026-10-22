---
id: TASK-117
title: Compact E2E Pipeline Combination Test Suite Under 400 Lines
type: test_contract
status: done
traces_to:
- REQ-046
- SPEC-046
depends_on:
- TASK-115
required_files:
- tests/test_pipeline_combinations.py
write_files:
- tests/test_pipeline_combinations.py
verification_cmd: pytest -q tests/test_task_runner.py -k test_modular_refactoring_and_file_size_ceilings
---
## Objective
Compact `tests/test_pipeline_combinations.py` so it stays at or below the 400-line refactoring ceiling (`refactor_target_file_lines: 400`) after `ruff format` while preserving all 7 E2E pipeline combination scenarios and `@traces` annotations.

## Scoped Instructions
- Keep `tests/test_pipeline_combinations.py` at or below 400 lines after `ruff format`.
- Preserve `MockTurn`, `PipelineScenario`, `PIPELINE_SCENARIOS`, and `test_declarative_pipeline_combinations_matrix` with `@traces("REQ-046", "AC-01", "SPEC-046")`, `@traces("REQ-046", "AC-02", "SPEC-046")`, and `@traces("REQ-046", "AC-03", "SPEC-046")`.
