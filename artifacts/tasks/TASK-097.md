---
id: TASK-097
title: Add TestContracts for Subgraph-Scoped Multi-REQ and Multi-SPEC Traceability
type: test_contract
status: done
traces_to:
- REQ-038
- SPEC-038
depends_on: []
required_files:
- artifacts/requirements/REQ-038.md
- artifacts/specifications/SPEC-038.md
- tests/test_traceability_and_cli.py
write_files:
- tests/test_traceability_and_cli.py
verification_cmd: python3 -m py_compile tests/test_traceability_and_cli.py
---
## Objective
Add `@traces("REQ-038", ...)` TestContracts in `tests/test_traceability_and_cli.py` verifying subgraph-scoped `TRACE_UNCOVERED_REQ_AC` and `TRACE_UNPLANNED_TARGET_FILE` checks across good, edge, and failure cases.

## Scoped Instructions
- Add `test_scoped_multi_req_and_spec_traceability_checks` in `tests/test_traceability_and_cli.py` decorated with `@traces("REQ-038", "AC-01", "SPEC-038")`, `@traces("REQ-038", "AC-02", "SPEC-038")`, and `@traces("REQ-038", "AC-03", "SPEC-038")`.
