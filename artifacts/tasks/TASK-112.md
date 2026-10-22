---
id: TASK-112
title: Split Orchestrator Prompt, Documentation, and Review Gate TestContracts
type: test_contract
status: ready
traces_to:
  - REQ-045
  - SPEC-045
depends_on:
  - TASK-111
required_files:
  - tests/test_orchestrator.py
  - tests/test_interaction_logging.py
  - tests/test_stage_runner.py
write_files:
  - tests/test_orchestrator.py
  - tests/test_interaction_logging.py
  - tests/test_stage_runner.py
  - tests/test_prompt_builder.py
  - tests/test_documentation_generator.py
  - tests/test_review_gates.py
verification_cmd: "python3 -m py_compile tests/test_orchestrator.py tests/test_interaction_logging.py tests/test_stage_runner.py tests/test_prompt_builder.py tests/test_documentation_generator.py tests/test_review_gates.py"
---
## Objective
Extract prompt synthesis, live documentation, and review gate `TestContract` functions into dedicated single-concern test modules below `400` lines.

## Scoped Instructions
Trim `tests/test_orchestrator.py`, `tests/test_interaction_logging.py`, and `tests/test_stage_runner.py`, and create `tests/test_prompt_builder.py` (adding `test_planner_single_concern_decomposition_contract` decorated with `@traces("REQ-045", "AC-02", "SPEC-045")`), `tests/test_documentation_generator.py`, and `tests/test_review_gates.py`.
