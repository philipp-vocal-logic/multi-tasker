---
id: TASK-150
title: Remove Unused jsonschema from DEFAULT_PYTHON_ARCHITECTURE in lifecycle
type: implementation
status: ready
traces_to:
- REQ-057
- SPEC-057
depends_on:
- TASK-149
required_files:
- tests/test_architecture_checker.py
- src/multi_tasker/orchestrator/lifecycle.py
write_files:
- src/multi_tasker/orchestrator/lifecycle.py
verification_cmd: pytest -q tests/test_architecture_checker.py
---
## Objective
Remove `"jsonschema"` from `DEFAULT_PYTHON_ARCHITECTURE["allowed_third_party_packages"]` in `src/multi_tasker/orchestrator/lifecycle.py`.

## Scoped Instructions
- Update `DEFAULT_PYTHON_ARCHITECTURE["allowed_third_party_packages"]` in `src/multi_tasker/orchestrator/lifecycle.py` to `["yaml", "pytest", "multi_tasker"]` matching `policy/code_architecture.yaml`.
