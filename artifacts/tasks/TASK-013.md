---
id: TASK-013
title: Implement Prompt Builder, MergeGate Timeout, and Lifecycle Approval for SPEC-004
type: implementation
status: done
traces_to: [REQ-004, SPEC-004]
depends_on: [TASK-012]
required_files:
  - tests/test_orchestrator.py
  - tests/test_lifecycle.py
write_files:
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/merge_gate.py
  - src/multi_tasker/orchestrator/lifecycle.py
verification_cmd: "pytest -q tests/test_orchestrator.py"
---
## Objective
Implement `src/multi_tasker/orchestrator/prompt_builder.py`, subprocess timeouts in `src/multi_tasker/orchestrator/merge_gate.py` and `src/multi_tasker/orchestrator/lifecycle.py`, and upstream `Intent` status transitions in `approve_artifact`.

## Scoped Instructions
Ensure all functions respect sizing limits (`max_function_lines: 40`) and pass `mt check clean_code` and `mt check limits`.
