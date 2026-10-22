---
id: SPEC-046
title: Declarative Pipeline Review Retry, Auto-Rerouting, and E2E Matrix Specification
status: approved
traces_to:
- REQ-046
covers_criteria:
- REQ-046:AC-01
- REQ-046:AC-02
- REQ-046:AC-03
decisions: []
target_files:
  tests:
  - tests/test_pipeline_combinations.py
  implementation:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Extend `router.py` and `stage_runner.py` so `run_declarative_pipeline` resets review-rejected artifacts (`STAGE_REVIEW_REJECTED`) to `draft` or `blocked` and re-triggers the stage agent up to `max_review_cycles`, and continues on `GATE_TASK_ESCALATED` when an `Escalation` is `routed_to_agent`. Inline failed `ReviewRecords`, rejected drafts, and `ESC` `affected_artifacts` in `prompt_context.py`, and restore `before_snapshot` files during stage normalization in `parser.py`.

## Public Interfaces
```python
def handle_pipeline_step_outcome(
    repository_root: Path,
    produced: list[str],
    findings: list[Finding],
) -> tuple[list[str], list[Finding], bool]: ...
```

## Test Contract Mapping
- `REQ-046:AC-01` -> `tests/test_pipeline_combinations.py::test_declarative_pipeline_combinations_matrix`
- `REQ-046:AC-02` -> `tests/test_pipeline_combinations.py::test_declarative_pipeline_combinations_matrix`
- `REQ-046:AC-03` -> `tests/test_pipeline_combinations.py::test_declarative_pipeline_combinations_matrix`
