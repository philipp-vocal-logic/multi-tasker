---
id: SPEC-037
title: Multi-Requirement Intent Completion Guard and Multi-Artifact Stage Review Specification
status: approved
traces_to:
- REQ-037
covers_criteria:
- REQ-037:AC-01
- REQ-037:AC-02
- REQ-037:AC-03
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
In `lifecycle.py`, extract `_sync_upstream_intents` so approving a `Requirement` checks all `REQ` artifacts in the repository tracing to each upstream `Intent`: if all linked `REQ`s are `approved`, transition the `Intent` to `processed`; if any sibling `REQ` remains unapproved, transition an `open` `Intent` to `processing`. In `stage_runner.py`, update `_step_declarative_stage` to run `review-agent` and `evaluate_review_verdict` on every produced stage artifact when `approval_gate == "review-agent"`, halting before approval if any artifact fails review.

## Public Interfaces
```python
def approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]:
    """Approve a Requirement, Specification, or Decision and mark downstream dirty."""


def run_declarative_pipeline(
    repository_root: Path,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
) -> tuple[list[str], list[Finding]]:
    """Step through policy/pipeline.yaml stages and auto-routed Escalations."""
```

## Test Contract Mapping
- `REQ-037:AC-01`: `tests/test_lifecycle.py::test_multi_requirement_intent_processing_and_completion` and `tests/test_stage_runner.py::test_multi_artifact_stage_review_pass_and_second_artifact_rejection` verify `INT` transitions to `processed` when all linked `REQ`s are approved and all produced stage artifacts are reviewed and approved.
- `REQ-037:AC-02`: `tests/test_lifecycle.py::test_multi_requirement_intent_processing_and_completion` verifies approving the first of two `REQ`s transitions `INT-001` from `open` to `processing`.
- `REQ-037:AC-03`: `tests/test_stage_runner.py::test_multi_artifact_stage_review_pass_and_second_artifact_rejection` verifies `review-agent` rejecting the second produced artifact halts approval and emits `STAGE_REVIEW_REJECTED`.
