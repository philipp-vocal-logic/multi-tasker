---
id: TASK-074
title: Support Package Prefix Relocation in Task Commit Scope Traceability Check
type: implementation
status: done
traces_to:
- REQ-026
- SPEC-026
depends_on:
- TASK-072
required_files:
- tests/test_transitions_and_execution.py
- src/multi_tasker/checkers/code_and_git_traceability.py
write_files:
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -q tests/test_traceability_and_cli.py
---
## Objective
Update `_check_task_commit_scope` in `src/multi_tasker/checkers/code_and_git_traceability.py` to recognize historical commits recorded before `src/<package>/...` relocation.

## Scoped Instructions
Expand `allowed_writes` in `_check_task_commit_scope` so `src/<package>/<subpackage>/...` entries in `write_files` also match historical `src/<subpackage>/...` commit paths.
