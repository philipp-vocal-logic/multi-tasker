---
id: TASK-079
title: TestContracts for Wheel Policy Template Resolution
type: test_contract
status: done
traces_to:
- REQ-029
- SPEC-029
depends_on: []
required_files: []
write_files:
- tests/test_lifecycle.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py
---
## Objective
Add `@traces("REQ-029", "AC-01", "SPEC-029")` coverage in `tests/test_lifecycle.py` verifying `_resolve_policy_template_directory()` resolves packaged `policy_templates` when present.

## Scoped Instructions
Update `tests/test_lifecycle.py` to trace `REQ-029:AC-01` and assert `_resolve_policy_template_directory()` returns a valid directory containing `permissions.yaml`.
