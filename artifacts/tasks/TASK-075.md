---
id: TASK-075
title: TestContracts for Repository Initialization Presets
type: test_contract
status: done
traces_to:
- REQ-027
- SPEC-027
depends_on: []
required_files: []
write_files:
- tests/test_lifecycle.py
- tests/test_stage_runner.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py tests/test_stage_runner.py
---
## Objective
Add `@traces("REQ-027", ...)` TestContracts in `tests/test_lifecycle.py` and `tests/test_stage_runner.py` verifying default `python` preset architecture scaffolding, `--preset multi-tasker`, `[CLI_INVALID_PRESET]`, and greenfield `src/domain/p.py` E2E pipeline execution.

## Scoped Instructions
Update `tests/test_lifecycle.py` and `tests/test_stage_runner.py` to test `mt initialize` presets and `src/domain/p.py` in the real-Git pipeline test.
