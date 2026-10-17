---
id: TASK-043
title: Add TestContract for Pipeline Review Gate Verdicts and Review Traceability
type: test_contract
status: planned
traces_to:
  - REQ-015
  - SPEC-015
depends_on: []
required_files:
  - tests/test_stage_runner.py
write_files:
  - tests/test_stage_runner.py
verification_cmd: pytest -q tests/test_interaction_logging.py
---
## Objective
Add `@traces("REQ-015", "AC-01", "SPEC-015")` and `@traces("REQ-015", "AC-02", "SPEC-015")` test functions to `tests/test_stage_runner.py`.

## Scoped Instructions
Add `test_pipeline_review_gate_verdict_and_exhaustion_escalation` (`@traces("REQ-015", "AC-01", "SPEC-015")`) verifying `approval_gate: review-agent` transitions `SPEC` to `approved` and `TASK` to `ready` on `verdict: pass` and creates `review_exhausted` escalation on `verdict: fail` reaching `max_review_cycles`. Add `test_review_record_traceability_documentation_and_stage_gate_log` (`@traces("REQ-015", "AC-02", "SPEC-015")`) verifying `target_artifacts` validation, `.report/specification.md` Mermaid edges, and `merge_gate` event logging in `.report/logs/tasks/<ID>.jsonl`.
