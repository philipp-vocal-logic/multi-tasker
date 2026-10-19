---
id: SPEC-029
title: Wheel-Compatible Policy Template Resolution Specification
status: approved
traces_to:
- REQ-029
covers_criteria:
- REQ-029:AC-01
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Extract `_resolve_policy_template_directory() -> Path` in `src/multi_tasker/orchestrator/lifecycle.py` so `_scaffold_default_policies_and_gitignore` checks `Path(__file__).resolve().parents[1] / "policy_templates"` first (packaged wheel layout) and falls back to `Path(__file__).resolve().parents[3] / "policy"` (repository source checkout).

## Public Interfaces
- `src/multi_tasker/orchestrator/lifecycle.py`: `_resolve_policy_template_directory() -> Path`

## Test Contract Mapping
- `REQ-029:AC-01` -> `tests/test_lifecycle.py::test_initialize_presets_and_invalid_preset_finding`
