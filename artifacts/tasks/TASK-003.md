---
id: TASK-003
title: Implement Permissions, Schemas, and Glossary Checkers for SPEC-001
type: implementation
status: done
traces_to: [REQ-001, SPEC-001]
depends_on: [TASK-001, TASK-002]
required_files:
  - tests/test_checkers.py
write_files:
  - src/checkers/permissions_checker.py
  - src/checkers/schemas_checker.py
  - src/checkers/glossary_checker.py
verification_cmd: "pytest -q tests/test_checkers.py"
---
## Objective
Implement `permissions_checker.py`, `schemas_checker.py`, and `glossary_checker.py` in `src/checkers/` for `SPEC-001`.

## Scoped Instructions
Enforce `policy/permissions.yaml`, `policy/schemas.yaml`, and `policy/glossary.yaml` with zero-noise Findings output.
