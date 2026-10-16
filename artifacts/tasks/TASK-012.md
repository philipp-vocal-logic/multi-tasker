---
id: TASK-012
title: Create TestContract for REQ-004 and SPEC-004
type: test_contract
status: done
traces_to: [REQ-004, SPEC-004]
depends_on: []
required_files: []
write_files:
  - tests/test_orchestrator.py
  - tests/test_lifecycle.py
  - tests/test_traceability_and_cli.py
verification_cmd: "pytest -q"
---
## Objective
Create executable `TestContract` tests in `tests/test_orchestrator.py`, `tests/test_lifecycle.py`, and `tests/test_traceability_and_cli.py` covering `REQ-004:AC-01` through `REQ-004:AC-03`.

## Scoped Instructions
Decorate each test with `@traces("REQ-004", "AC-XX", "SPEC-004")` and verify `MergeGate` verification timeouts, role prompt synthesis (`mt prompt`), Worktree `MT_PROMPT_FILE` delivery, `Intent` processing on approval, and commit `WriteScope` traceability.
