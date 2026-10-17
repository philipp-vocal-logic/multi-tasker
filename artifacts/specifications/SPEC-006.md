---
id: SPEC-006
title: Continual Report Documentation Generation Specification
status: approved
traces_to: [REQ-006]
covers_criteria:
  - REQ-006:AC-01
  - REQ-006:AC-02
decisions: []
target_files:
  tests:
    - tests/test_orchestrator.py
  implementation:
    - src/orchestrator/documentation_generator.py
    - src/orchestrator/lifecycle.py
    - src/cli/main.py
---
## Design Overview
Add `write_repository_documentation` to `src/orchestrator/documentation_generator.py` to write `.report/.gitignore` (`*`) and `.report/specification.md` with the output of `generate_repository_documentation`. Invoke `write_repository_documentation` from `mt documentation` in `src/cli/main.py` and after `initialize_repository`, `create_intent`, `_mark_dirty_downstream` (`approve_artifact` and `resolve_escalation`), and `run_scheduled_tasks` in `src/orchestrator/lifecycle.py`.

## Public Interfaces
```python
def write_repository_documentation(repository_root: Path) -> Path: ...
```

## Test Contract Mapping
- `test_continual_report_documentation_generation` -> `REQ-006:AC-01`, `REQ-006:AC-02`
