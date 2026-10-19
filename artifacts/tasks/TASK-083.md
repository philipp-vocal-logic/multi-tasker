---
id: TASK-083
title: TestContracts for Streamlined Worker and Stage Role Prompts
type: test_contract
status: done
traces_to:
- REQ-031
- SPEC-031
depends_on: []
required_files: []
write_files:
- tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py
---
## Objective
Add `@traces("REQ-031", "AC-01", "SPEC-031")` and `@traces("REQ-031", "AC-02", "SPEC-031")` assertions in `tests/test_interaction_logging.py` verifying concrete `worker-agent` paths/commands and omission of `### TASK Output Contract`.

## Scoped Instructions
Update `_assert_self_contained_prompt_output` and `test_prompt_and_worktree_run_context_modes` in `tests/test_interaction_logging.py` to trace `REQ-031:AC-01` and `REQ-031:AC-02`.
