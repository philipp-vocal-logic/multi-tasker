---
id: TASK-070
title: Add TestContract for Fail-Fast Worker Task Scope and Check Paths
type: test_contract
status: planned
traces_to:
  - REQ-025
  - SPEC-025
depends_on: []
required_files:
  - artifacts/requirements/REQ-025.md
  - artifacts/specifications/SPEC-025.md
write_files:
  - tests/test_traceability_and_cli.py
verification_cmd: python3 -m py_compile tests/test_traceability_and_cli.py
---
## Objective
Add `test_fail_fast_worker_task_scope_and_explicit_check_paths` decorated with `@traces("REQ-025", "AC-01", "SPEC-025")` in `tests/test_traceability_and_cli.py`.

## Scoped Instructions
Verify `run_single_check("permissions", ...)` fails fast with `PERM_TASK_ID_MISSING` when `agent_role="worker-agent"` omits `task_id` even on empty diffs, forwards `target_paths` to `check_permissions`, and `build_agent_prompt` includes `--task <id>` for `worker-agent`.
