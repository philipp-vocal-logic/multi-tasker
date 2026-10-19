---
id: TASK-071
title: Implement Fail-Fast Worker Task Scope Validation and Explicit Check Arguments
type: implementation
status: done
traces_to:
- REQ-025
- SPEC-025
depends_on:
- TASK-070
required_files:
- artifacts/specifications/SPEC-025.md
- tests/test_traceability_and_cli.py
write_files:
- src/multi_tasker/checkers/runner.py
- src/multi_tasker/checkers/permissions_checker.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/task_runner.py
verification_cmd: pytest -q tests/test_traceability_and_cli.py tests/test_checkers.py
---
## Objective
Forward `target_paths` to `check_permissions` in `src/multi_tasker/checkers/runner.py`, fail fast on missing `worker-agent` `--task` even when `files` is empty in `src/multi_tasker/checkers/permissions_checker.py`, render `--task <target_id>` in `src/multi_tasker/orchestrator/prompt_builder.py`, and remove the dummy `task_id` fallback in `src/multi_tasker/orchestrator/task_runner.py`.

## Scoped Instructions
Keep all modified files under 400 lines and all functions within configured clean code limits.
