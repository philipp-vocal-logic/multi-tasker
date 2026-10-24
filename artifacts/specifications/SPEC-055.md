---
id: SPEC-055
title: Multi-Language E2E Pipeline Matrix, Multi-Task Review Retry, and Escalation
  Unblocking Specification
status: approved
traces_to:
- REQ-055
covers_criteria:
- REQ-055:AC-01
- REQ-055:AC-02
- REQ-055:AC-03
- REQ-055:AC-04
decisions: []
target_files:
  tests:
  - tests/test_multi_language_scenarios.py
  - tests/test_multi_language_workflows.py
  implementation:
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Harden declarative pipeline execution and add mocked E2E pipeline suites across Python, ANSI C, and Rust:
- Update `find_actionable_stage_target` in `router.py` so sibling `draft`/`blocked` downstream artifacts sharing an upstream with a failed review are included in `retry_pending`.
- Update `_mark_dirty_subgraph` and `resolve_escalation` in `router.py` to unblock `blocked` targets (`TASK` to `ready`, `REQ`/`SPEC` to `draft`) and append resolving `DEC` IDs to `decisions`.
- Update `_step_declarative_stage` in `stage_runner.py` to review all produced stage artifacts before invoking `approve_stage_artifact`.

## Public Interfaces
```python
def find_actionable_stage_target(repository_root: Path, stage: dict[str, Any]) -> str | None: ...
def resolve_escalation(repository_root: Path, escalation_id: str, resolved_by: str) -> list[Finding]: ...
```

## Test Contract Mapping
- `REQ-055:AC-01` -> `tests/test_multi_language_scenarios.py::test_multi_language_production_gate_topology_e2e`
- `REQ-055:AC-02` -> `tests/test_multi_language_scenarios.py::test_multi_language_review_retry_and_exhaustion_e2e`
- `REQ-055:AC-03` -> `tests/test_multi_language_scenarios.py::test_multi_language_escalation_reroute_and_decision_resolution_e2e`
- `REQ-055:AC-04` -> `tests/test_multi_language_workflows.py::test_multi_language_parallel_layers_and_merge_gate_faults_e2e`, `tests/test_multi_language_workflows.py::test_multi_language_requirement_supersession_e2e`
