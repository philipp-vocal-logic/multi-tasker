---
id: TASK-062
title: Support REV-* Identifiers in Git Commit Traceability Validation
type: implementation
status: done
traces_to:
- REQ-021
- SPEC-021
depends_on:
- TASK-060
- TASK-061
required_files:
- tests/test_stage_runner.py
- src/multi_tasker/checkers/code_and_git_traceability.py
write_files:
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -q tests/test_stage_runner.py
---
## Objective
Update `DEFAULT_COMMIT_PATTERN` and `ARTIFACT_ID_REGEX` in `src/multi_tasker/checkers/code_and_git_traceability.py` to support `REV-[A-Z0-9-]+` commit identifiers and verify `tests/test_stage_runner.py` passes.

## Scoped Instructions
- Update `DEFAULT_COMMIT_PATTERN` and `ARTIFACT_ID_REGEX` in `src/multi_tasker/checkers/code_and_git_traceability.py` so `REV-[A-Z0-9-]+` identifiers in commit subjects and `[traces: ...]` footers are matched and validated against `by_identifier`.
