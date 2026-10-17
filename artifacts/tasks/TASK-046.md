---
id: TASK-046
title: Fix Quote Escaping in Pipeline Review Gate TestContract Helper
type: test_contract
status: planned
traces_to:
  - REQ-015
  - SPEC-015
depends_on:
  - TASK-043
  - TASK-044
required_files:
  - tests/test_stage_runner.py
write_files:
  - tests/test_stage_runner.py
verification_cmd: pytest -q tests/test_interaction_logging.py
---
## Objective
Update `_PIPELINE_HELPER_SCRIPT` in `tests/test_stage_runner.py` so `worker-agent` test generation uses `chr(34)` instead of unescaped nested quotes.

## Scoped Instructions
Update `_PIPELINE_HELPER_SCRIPT` in `tests/test_stage_runner.py` to format `@traces(...)` using `chr(34)` so `pipeline_agent_helper.py` is valid Python.
