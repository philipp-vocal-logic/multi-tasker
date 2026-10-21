---
id: TASK-098
title: Implement Subgraph-Scoped Multi-REQ and Multi-SPEC Traceability Checks
type: implementation
status: done
traces_to:
- REQ-038
- SPEC-038
depends_on:
- TASK-097
required_files:
- artifacts/requirements/REQ-038.md
- artifacts/specifications/SPEC-038.md
- tests/test_traceability_and_cli.py
- src/multi_tasker/checkers/traceability_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
write_files:
- src/multi_tasker/checkers/traceability_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -o pythonpath=src -q tests/test_traceability_and_cli.py -k
  scoped_multi_req
---
## Objective
Scope `_check_requirement_to_specification_coverage` in `traceability_checker.py` and `check_specification_target_files` in `code_and_git_traceability.py` to the targeted `REQ`/`SPEC` subgraph when artifact `target_paths` are provided.

## Scoped Instructions
- In `traceability_checker.py`, filter checked `REQ` documents to those referenced in `traces_to` of targeted `SPEC`/`TASK` files when `target_paths` only contains `artifacts/**`.
- In `code_and_git_traceability.py`, filter checked `SPEC` documents for `TRACE_UNPLANNED_TARGET_FILE` to those referenced by targeted `TASK`/`SPEC` files when `target_paths` only contains `artifacts/**`.
