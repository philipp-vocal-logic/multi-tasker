---
id: TASK-115
title: Add Data-Driven E2E Pipeline Combination TestContracts
type: test_contract
status: ready
traces_to:
  - REQ-046
  - SPEC-046
depends_on: []
required_files:
  - artifacts/requirements/REQ-046.md
  - artifacts/specifications/SPEC-046.md
write_files:
  - tests/test_pipeline_combinations.py
verification_cmd: python3 -m py_compile tests/test_pipeline_combinations.py
---
## Objective
Create `tests/test_pipeline_combinations.py` with a data-driven E2E pipeline test harness and parametrized scenario matrix covering gate modes, review retries, review exhaustion, in-run escalation reroutes, and `MergeGate` fault isolation.

## Scoped Instructions
- Author `tests/test_pipeline_combinations.py` (under 400 lines) with `@traces("REQ-046", "AC-01", "SPEC-046")`, `@traces("REQ-046", "AC-02", "SPEC-046")`, and `@traces("REQ-046", "AC-03", "SPEC-046")` on `test_declarative_pipeline_combinations_matrix`.
- Define `MockTurn` and `PipelineScenario` dataclasses and a mock model dispatcher that verifies `.mt_prompt.md` substrings and writes scripted turn outputs per `(role, target_id, attempt)`.
- Parametrize scenarios for `auto`/`human`/`review-agent` gates, 1-fail-then-pass review retry, `review_exhausted` escalation, in-run `infeasible_scope` `planner-agent` rerouting, `reroute_limit_reached`, and `MergeGate` rejection isolation.
