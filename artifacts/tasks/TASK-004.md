---
id: TASK-004
title: Implement Limits, Clean Code, and Architecture Checkers for SPEC-001
type: implementation
status: done
traces_to: [REQ-001, SPEC-001]
depends_on: [TASK-001, TASK-002]
required_files:
  - tests/test_traceability_and_cli.py
write_files:
  - src/checkers/limits_checker.py
  - src/checkers/clean_code_checker.py
  - src/checkers/architecture_checker.py
verification_cmd: "pytest -q tests/test_traceability_and_cli.py"
---
## Objective
Implement `limits_checker.py`, `clean_code_checker.py`, and `architecture_checker.py` in `src/checkers/` for `SPEC-001`.

## Scoped Instructions
Enforce `policy/limits.yaml`, `policy/clean_code.yaml`, and `policy/architecture.yaml` across `src/**` and `tests/**`.
