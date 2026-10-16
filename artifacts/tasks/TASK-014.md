---
id: TASK-014
title: Implement Commit WriteScope Traceability and CLI Prompt Subcommand for SPEC-004
type: implementation
status: done
traces_to: [REQ-004, SPEC-004]
depends_on: [TASK-012, TASK-013]
required_files:
  - tests/test_lifecycle.py
  - tests/test_traceability_and_cli.py
write_files:
  - src/checkers/common.py
  - src/checkers/traceability_checker.py
  - src/cli/main.py
verification_cmd: "pytest -q"
---
## Objective
Implement `get_git_commit_files` in `src/checkers/common.py`, commit `WriteScope` and `Intent` coverage checks in `src/checkers/traceability_checker.py`, and `mt prompt` CLI wiring in `src/cli/main.py`.

## Scoped Instructions
Ensure full compliance with all `policy/*.yaml` rules and verify `mt check all` and `pytest -q` pass with zero findings.
