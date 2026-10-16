---
id: TASK-011
title: Implement CLI Main Entrypoint and Command Dispatch for SPEC-001 and SPEC-003
type: implementation
status: done
traces_to: [REQ-001, SPEC-001, REQ-003, SPEC-003]
depends_on: [TASK-001, TASK-009, TASK-010]
required_files:
  - tests/test_lifecycle.py
write_files:
  - src/cli/main.py
verification_cmd: "pytest -q"
---
## Objective
Implement `src/cli/main.py` wiring all `mt` subcommands (`check`, `schedule`, `impact`, `initialize`, `intent`, `approve`, `resolve`, `run`, `trace`, `documentation`).

## Scoped Instructions
Follow all `policy/*.yaml` constraints and maintain zero-noise CLI output across all subcommands.
