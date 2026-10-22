---
id: SPEC-043
title: Parallel Worker Execution in Declarative Pipeline Mode Specification
status: approved
traces_to:
- REQ-043
covers_criteria:
- REQ-043:AC-01
- REQ-043:AC-02
- REQ-043:AC-03
decisions: []
target_files:
  tests:
  - tests/test_stage_escalation.py
  implementation:
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Extend `run_declarative_pipeline` and `_step_declarative_stage` in `src/multi_tasker/orchestrator/stage_runner.py` with `max_workers: int = 1` and pass `max_workers` into `run_scheduled_tasks` when `role == "worker-agent"`. Update `_dispatch_run_target` in `src/multi_tasker/cli/main.py` to forward `int(getattr(arguments, "max_workers", 1))` to `run_declarative_pipeline`.

## Public Interfaces
```python
def run_declarative_pipeline(
    repository_root: Path,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
    max_workers: int = 1,
) -> tuple[list[str], list[Finding]]:
    """Step through policy/pipeline.yaml stages and auto-routed Escalations."""
```

## Test Contract Mapping
- `REQ-043:AC-01` -> `tests/test_stage_escalation.py::test_declarative_pipeline_max_workers_forwarding_and_failure_halt`
- `REQ-043:AC-02` -> `tests/test_stage_escalation.py::test_declarative_pipeline_max_workers_forwarding_and_failure_halt`
- `REQ-043:AC-03` -> `tests/test_stage_escalation.py::test_declarative_pipeline_max_workers_forwarding_and_failure_halt`
