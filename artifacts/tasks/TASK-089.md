---
id: TASK-089
title: TestContracts for Non-Fixed Prompt Example IDs, 88-Char Line Length, and Glossary Terms
type: test_contract
status: ready
traces_to:
- REQ-034
- SPEC-034
depends_on: []
required_files:
- artifacts/requirements/REQ-034.md
- artifacts/specifications/SPEC-034.md
- src/multi_tasker/orchestrator/prompt_builder.py
write_files:
- tests/test_interaction_logging.py
verification_cmd: python3 -m py_compile tests/test_interaction_logging.py
---
## Objective
Add `TestContract` assertions in `tests/test_interaction_logging.py` for `REQ-034:AC-01` and `REQ-034:AC-02` covering non-fixed prompt example identifiers, 88-character prompt instruction line wrapping, `max_line_length=88`, and canonical `Glossary` terms.

## Scoped Instructions
1. Decorate `test_prompt_and_worktree_run_context_modes` in `tests/test_interaction_logging.py` with `@traces("REQ-034", "AC-01", "SPEC-034")` and `@traces("REQ-034", "AC-02", "SPEC-034")`.
2. Assert that targetless role prompts and output contract skeletons use `REQ-NNN`, `ESC-NNN`, and `AC-XX` (and not `id: ESC-001`), that all instruction lines in targetless role prompts have length `<= 88`, that `worker-agent` `Source Limits` include `max_line_length=88`, and that `Glossary Terms` with `code_identifiers` are rendered.
