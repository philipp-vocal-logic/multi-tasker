---
id: TASK-144
title: Add Multi-Language Gate, Review Retry, and Escalation TestContracts
type: test_contract
status: done
traces_to:
- REQ-055
- SPEC-055
depends_on: []
required_files:
- tests/test_multi_language_pipeline.py
- tests/test_pipeline_combinations.py
write_files:
- tests/test_multi_language_scenarios.py
verification_cmd: python3 -m py_compile tests/test_multi_language_scenarios.py
---
## Objective
Create `tests/test_multi_language_scenarios.py` with `@traces("REQ-055", ...)` E2E tests across Python, ANSI C, and Rust for production gates, review retries, and escalations.

## Scoped Instructions
- Exercise `human`, `review-agent`, and `auto` stage gates, SPEC and multi-task planning review rejection/retry and exhaustion (`STAGE_REVIEW_EXHAUSTED`), worker `infeasible_scope` auto-rerouting, and `ambiguity` escalation resolution via `mt resolve` across all three languages.
