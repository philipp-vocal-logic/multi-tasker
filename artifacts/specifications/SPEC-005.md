---
id: SPEC-005
title: CLI Execution Environment and Model Resolution Specification
status: approved
traces_to: [REQ-005]
covers_criteria:
  - REQ-005:AC-01
  - REQ-005:AC-02
decisions: []
target_files:
  tests:
    - tests/test_lifecycle.py
  implementation:
    - src/checkers/permissions_checker.py
    - src/orchestrator/prompt_builder.py
    - src/orchestrator/lifecycle.py
    - src/cli/main.py
---
## Design Overview
Extend `src/checkers/permissions_checker.py` to validate `execution_environments` in `policy/permissions.yaml`, add `ExecutionConfiguration` and `resolve_task_execution` in `src/orchestrator/prompt_builder.py` for CLI/Task/Policy model and environment resolution (`agy` headless mode with `gemini-3.8-flash-high`), and wire `--model` and `--environment` into `mt run` (`src/orchestrator/lifecycle.py` and `src/cli/main.py`).

## Public Interfaces
```python
def resolve_task_execution(repository_root: Path, document: ArtifactDocument, options: tuple[str | None, str | None, str | None] = (None, None, None)) -> tuple[str | None, str, str]: ...
```

## Test Contract Mapping
- `test_execution_environment_and_model_resolution` -> `REQ-005:AC-01`, `REQ-005:AC-02`
