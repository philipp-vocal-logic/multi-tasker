---
id: TASK-091
title: Add TestContracts for Cross-Stage Prompt Alignment and Worker Output Contract
type: test_contract
status: ready
traces_to:
  - REQ-035
  - SPEC-035
depends_on: []
required_files:
  - artifacts/requirements/REQ-035.md
  - artifacts/specifications/SPEC-035.md
  - tests/test_interaction_logging.py
write_files:
  - tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py
---

## Objective
Extend `tests/test_interaction_logging.py` with `@traces("REQ-035", ...)` assertions verifying cross-stage `Source Limits`, the `WorkerAgent` Python Output Contract, Section 4 file deduplication and new-file status, and concrete stage output paths.

## Scoped Instructions
- Add `@traces("REQ-035", "AC-01", "SPEC-035")`, `@traces("REQ-035", "AC-02", "SPEC-035")`, and `@traces("REQ-035", "AC-03", "SPEC-035")` to `test_prompt_and_worktree_run_context_modes` in `tests/test_interaction_logging.py`.
- Assert `specification-agent`, `planner-agent`, `worker-agent`, and `review-agent` prompts include `Source Limits` and `Clean Code AST Rules`.
- Assert `worker-agent` prompts render `### Python Source & TestContract Output Contract` and `Status: New file` for non-existent `write_files`, and targeted stage prompts resolve concrete output paths.
