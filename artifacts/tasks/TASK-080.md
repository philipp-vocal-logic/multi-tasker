---
id: TASK-080
title: Implement Wheel Policy Template Resolution in Lifecycle
type: implementation
status: done
traces_to:
- REQ-029
- SPEC-029
depends_on:
- TASK-079
required_files:
- tests/test_lifecycle.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
verification_cmd: pytest -o pythonpath=src -q tests/test_lifecycle.py
---
## Objective
Implement `_resolve_policy_template_directory()` in `src/multi_tasker/orchestrator/lifecycle.py` so `initialize_repository` works from both wheel installs and source checkouts.

## Scoped Instructions
Add `_resolve_policy_template_directory()` in `src/multi_tasker/orchestrator/lifecycle.py` and call it in `_scaffold_default_policies_and_gitignore`.
