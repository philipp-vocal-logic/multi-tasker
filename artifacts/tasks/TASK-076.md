---
id: TASK-076
title: Implement Policy Presets in Repository Initialization and CLI
type: implementation
status: ready
traces_to:
- REQ-027
- SPEC-027
depends_on:
- TASK-075
required_files:
- tests/test_lifecycle.py
- tests/test_stage_runner.py
write_files:
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/lifecycle.py
verification_cmd: pytest -o pythonpath=src -q tests/test_lifecycle.py tests/test_stage_runner.py
---
## Objective
Implement `--preset` (`python` default, `multi-tasker`) in `src/multi_tasker/orchestrator/lifecycle.py` and `src/multi_tasker/cli/main.py` and emit `[CLI_INVALID_PRESET]` on unknown presets.

## Scoped Instructions
Update `initialize_repository` and `_scaffold_default_policies_and_gitignore` in `src/multi_tasker/orchestrator/lifecycle.py` and the `initialize` CLI parser/dispatcher in `src/multi_tasker/cli/main.py`.
