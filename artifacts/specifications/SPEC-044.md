---
id: SPEC-044
title: Deprecation of Legacy Context Mode Requirement and Documentation Specification
status: approved
traces_to:
- REQ-044
covers_criteria:
- REQ-044:AC-01
- REQ-044:AC-02
- REQ-044:AC-03
decisions: []
target_files:
  tests:
  - tests/test_stage_escalation.py
  implementation:
  - src/multi_tasker/orchestrator/documentation_generator.py
---
## Design Overview
Approve `REQ-044` with `supersedes: [REQ-012]` so `approve_artifact` transitions `REQ-012` and `SPEC-012` to `deprecated`. Update `README.md` to remove `default_context_mode` and `[--context-mode inline|paths]`, and update `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to include `mt prompt <agent-role> [--target <id>]`.

## Public Interfaces
```python
def generate_external_agents_guide() -> str:
    """Synthesize external project AGENTS.md bootstrapping and policy tuning guide."""
```

## Test Contract Mapping
- `REQ-044:AC-01` -> `tests/test_stage_escalation.py::test_legacy_context_mode_deprecation_and_documentation_alignment`
- `REQ-044:AC-02` -> `tests/test_stage_escalation.py::test_legacy_context_mode_deprecation_and_documentation_alignment`
- `REQ-044:AC-03` -> `tests/test_stage_escalation.py::test_legacy_context_mode_deprecation_and_documentation_alignment`
