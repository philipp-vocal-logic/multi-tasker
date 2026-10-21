---
id: TASK-087
title: TestContracts for Compact Templates, Layer Imports, and Role-Tailored Prompts
type: test_contract
status: ready
traces_to:
  - REQ-033
  - SPEC-033
depends_on: []
required_files:
  - src/multi_tasker/orchestrator/prompt_builder.py
write_files:
  - tests/test_interaction_logging.py
verification_cmd: "python3 -m py_compile tests/test_interaction_logging.py"
---
## Objective
Extend `tests/test_interaction_logging.py` (`test_prompt_and_worktree_run_context_modes`) with `@traces("REQ-033", "AC-01", "SPEC-033")` and `@traces("REQ-033", "AC-02", "SPEC-033")` assertions covering compact frontmatter-and-section templates, 3-line `ESC` contracts, layer `imports:`, role-specific `Execution Steps` Step 1, and `SPEC` `target_files` context injection.

## Scoped Instructions
Update `_assert_self_contained_prompt_output` and `test_prompt_and_worktree_run_context_modes` in `tests/test_interaction_logging.py` to assert that `build_agent_prompt` omits raw `json_schema:` / `additionalProperties:` dumps, includes frontmatter `---` and `## Statement` in `requirement-agent` output, omits `@traces` from `requirement-agent`, includes `imports:` in `Architecture Layers`, and inlines `target_files` when `review-agent` targets `SPEC-001`.
