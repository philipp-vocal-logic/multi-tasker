---
id: TASK-039
title: Create TestContract for Declarative Pipeline Policy and Execution
type: test_contract
status: planned
traces_to:
  - REQ-014
  - SPEC-014
depends_on: []
required_files:
  - policy/pipeline.yaml
write_files:
  - tests/test_stage_runner.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Add `TestContract` tests for `policy/pipeline.yaml` schema validation, configurable `Escalation` routing, and `mt run --pipeline` execution in `tests/test_stage_runner.py`.

## Scoped Instructions
Extend `tests/test_stage_runner.py` with `test_pipeline_policy_validation_and_configurable_escalation_routing` (`@traces("REQ-014", "AC-01", "SPEC-014")`) and `test_declarative_pipeline_execution_gates_and_auto_escalation` (`@traces("REQ-014", "AC-02", "SPEC-014")`). Seed `policy/pipeline.yaml` in synthetic test repositories and verify stage execution, `approval_gate` handling, and `routed_to_agent` `Escalation` self-healing.
