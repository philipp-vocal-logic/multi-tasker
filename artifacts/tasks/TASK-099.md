---
id: TASK-099
title: Add TestContracts for Requirement Supersession and Deprecation Lifecycle
type: test_contract
status: ready
traces_to:
  - REQ-039
  - SPEC-039
depends_on: []
required_files:
  - artifacts/requirements/REQ-039.md
  - artifacts/specifications/SPEC-039.md
write_files:
  - tests/test_lifecycle.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py
---
## Objective
Add `TestContract` coverage in `tests/test_lifecycle.py` for `REQ-039:AC-01`, `REQ-039:AC-02`, and `REQ-039:AC-03`.

## Scoped Instructions
Add `test_requirement_supersession_deprecates_old_req_and_spec` decorated with `@traces("REQ-039", "AC-01", "SPEC-039")`, `@traces("REQ-039", "AC-02", "SPEC-039")`, and `@traces("REQ-039", "AC-03", "SPEC-039")` verifying `supersedes` approval auto-deprecation, `check_traceability` deprecated upstream handling, and catalog/metric filtering of deprecated `Requirement` artifacts.
