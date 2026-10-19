---
id: TASK-026
title: Extract Code and Git Traceability Module from Traceability Checker for SPEC-009
type: implementation
status: done
traces_to:
- REQ-009
- SPEC-009
depends_on:
- TASK-024
- TASK-025
required_files:
- tests/test_transitions_and_execution.py
- src/multi_tasker/orchestrator/task_runner.py
write_files:
- src/multi_tasker/checkers/traceability_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -q
---
## Objective
Extract `TestContract`, `target_files`, and Git commit `Traceability` validation from `src/multi_tasker/checkers/traceability_checker.py` into `src/multi_tasker/checkers/code_and_git_traceability.py`.

## Scoped Instructions
Create `src/multi_tasker/checkers/code_and_git_traceability.py` exposing `check_test_contract_coverage`, `check_specification_target_files`, and `check_git_commit_history`, and update `src/multi_tasker/checkers/traceability_checker.py` to delegate to those functions with zero re-exports.
