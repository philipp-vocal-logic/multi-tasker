---
id: SPEC-015
title: Pipeline Review Gate Verdict Enforcement and Review Traceability Specification
status: approved
traces_to:
- REQ-015
covers_criteria:
- REQ-015:AC-01
- REQ-015:AC-02
decisions: []
target_files:
  tests:
  - tests/test_stage_runner.py
  implementation:
  - src/checkers/traceability_checker.py
  - src/orchestrator/documentation_generator.py
  - src/orchestrator/lifecycle.py
  - src/orchestrator/stage_runner.py
---
## Design Overview
Configure `max_review_cycles: 2` and `approval_gate: "review-agent"` on `requirement_to_specification` and `specification_to_tasks` in `policy/pipeline.yaml`. Update `src/orchestrator/stage_runner.py` to evaluate `ReviewRecord` (`REV-*.md`) verdicts (`pass` transitions `REQ`/`SPEC` to `approved` and `TASK` to `ready`; `fail` emits `STAGE_REVIEW_REJECTED` or escalates via `review_exhausted` when `max_review_cycles` is reached) and log `merge_gate` events in `run_agent_stage`. Wire `target_artifacts` into `src/checkers/traceability_checker.py` and `src/orchestrator/documentation_generator.py`.

## Public Interfaces
- `policy/pipeline.yaml`:
  - `execution_bounds.max_review_cycles: 2`
  - `stages[requirement_to_specification].approval_gate: "review-agent"`
  - `stages[specification_to_tasks].approval_gate: "review-agent"`
- `src/orchestrator/stage_runner.py`:
  - `_evaluate_review_gate(repository_root: Path, artifact_id: str, options: tuple[str | None, str | None, str | None]) -> tuple[list[str], list[Finding]]`
  - `_create_review_escalation(repository_root: Path, artifact_id: str, rev_path: str) -> list[Finding]`
  - `_approve_stage_artifact(repository_root: Path, artifact_id: str) -> None`
- `src/checkers/traceability_checker.py`:
  - `LIST_REFERENCE_FIELDS` includes `"target_artifacts"`
- `src/orchestrator/documentation_generator.py`:
  - `_append_artifact_trace_edges` renders `REV-*` stage/verdict labels and `target_artifacts` dotted edges.

## Test Contract Mapping
- `REQ-015:AC-01` $\rightarrow$ `tests/test_stage_runner.py::test_pipeline_review_gate_verdict_and_exhaustion_escalation`
- `REQ-015:AC-02` $\rightarrow$ `tests/test_stage_runner.py::test_review_record_traceability_documentation_and_stage_gate_log`
