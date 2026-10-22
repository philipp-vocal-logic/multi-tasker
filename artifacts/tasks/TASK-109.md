---
id: TASK-109
title: Add TestContracts for Legacy Context Mode Deprecation and Documentation Alignment
type: test_contract
status: done
traces_to:
- REQ-044
- SPEC-044
depends_on: []
required_files:
- artifacts/requirements/REQ-044.md
- artifacts/specifications/SPEC-044.md
write_files:
- tests/test_stage_escalation.py
verification_cmd: python3 -m py_compile tests/test_stage_escalation.py
---
## Objective
Add `TestContracts` in `tests/test_stage_escalation.py` covering `REQ-044:AC-01`, `REQ-044:AC-02`, and `REQ-044:AC-03` for `SPEC-044`.

## Scoped Instructions
Append `test_legacy_context_mode_deprecation_and_documentation_alignment` decorated with `@traces("REQ-044", "AC-01", "SPEC-044")`, `@traces("REQ-044", "AC-02", "SPEC-044")`, and `@traces("REQ-044", "AC-03", "SPEC-044")` to `tests/test_stage_escalation.py`.
