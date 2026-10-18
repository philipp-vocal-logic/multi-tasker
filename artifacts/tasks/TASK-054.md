---
id: TASK-054
title: Add TestContract for 500-Line Hard Limit and 400-Line Refactoring Target Warnings
type: test_contract
status: planned
traces_to:
- REQ-018
- SPEC-018
depends_on: []
required_files:
- tests/test_transitions_and_execution.py
write_files:
- tests/test_transitions_and_execution.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Update `test_modular_refactoring_and_file_size_ceilings` in `tests/test_transitions_and_execution.py` with `@traces("REQ-018", "AC-01", "SPEC-018")` and `@traces("REQ-018", "AC-02", "SPEC-018")` to enforce `max_file_lines` (`500`) from `policy/limits.yaml` and verify `400`-line non-blocking refactoring target warnings in planning prompts.

## Scoped Instructions
In `tests/test_transitions_and_execution.py`, decorate `test_modular_refactoring_and_file_size_ceilings` with `@traces("REQ-018", "AC-01", "SPEC-018")` and `@traces("REQ-018", "AC-02", "SPEC-018")`, replace the hardcoded `360` ceiling with `max_file_lines` (`500`) read from `policy/limits.yaml`, and verify in a `tmp_path` fixture that a `405`-line Python file passes `check_limits` with zero blocking `Findings` while `collect_refactoring_targets` emits `LIMIT_REFACTOR_HINT` and `build_agent_prompt` for `planner-agent` and `specification-agent` includes `Refactoring Targets (Warning)`.
