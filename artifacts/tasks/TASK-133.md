---
id: TASK-133
title: Add TestContracts for Policy-Driven Extensions, Ephemeral Globs, Forbidden Calls, and Test Commands
type: test_contract
status: ready
traces_to:
- REQ-051
- SPEC-051
depends_on: []
required_files:
- tests/test_clean_code_checker.py
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_prompt_builder.py
write_files:
- tests/test_clean_code_checker.py
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_prompt_builder.py
verification_cmd: python3 -m py_compile tests/test_clean_code_checker.py tests/test_lifecycle.py
  tests/test_orchestrator.py tests/test_prompt_builder.py
---
## Objective
Add `@traces("REQ-051", ...)` TestContracts verifying policy-driven `ignored_ephemeral_globs`, `language`/`source_extensions`, `forbidden_calls_in_src`, `test_file_glob`, and planner verification commands.

## Scoped Instructions
- Tag `test_clean_code_checker_violation_branches` and `test_output_contract_mypy_and_toggle_sensitivity` in `tests/test_clean_code_checker.py` with `@traces("REQ-051", "AC-02", "SPEC-051")` and test `forbidden_calls_in_src` and `source_extensions`.
- Tag `test_initialize_and_intent_creation_with_git` in `tests/test_lifecycle.py` with `@traces("REQ-051", "AC-01", "SPEC-051")` and verify `ignored_ephemeral_globs` filtering.
- Tag `test_all_policy_yaml_keys_are_enforced_and_read` in `tests/test_orchestrator.py` and `test_planner_single_concern_decomposition_contract` in `tests/test_prompt_builder.py` with `@traces("REQ-051", ...)` and verify custom verification commands from `policy/traceability.yaml`.
