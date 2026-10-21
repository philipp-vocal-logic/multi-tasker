---
id: TASK-093
title: Add TestContracts for Atomic Requirement Decomposition Prompt and Catalog
type: test_contract
status: planned
traces_to:
  - REQ-036
  - SPEC-036
depends_on: []
required_files:
  - artifacts/requirements/REQ-036.md
  - artifacts/specifications/SPEC-036.md
  - tests/test_orchestrator.py
write_files:
  - tests/test_orchestrator.py
verification_cmd: python3 -m py_compile tests/test_orchestrator.py
---
## Objective
Add `@traces("REQ-036", ...)` TestContracts in `tests/test_orchestrator.py` verifying the `Requirement Decomposition Contract`, `Existing Requirements Catalog`, targetless/empty-repository behavior, and `ReviewAgent` `Semantic Review Rubric` atomicity and good/edge/failure AC checks.

## Scoped Instructions
- Add `test_atomic_requirement_decomposition_prompt_and_catalog` in `tests/test_orchestrator.py` decorated with `@traces("REQ-036", "AC-01", "SPEC-036")`, `@traces("REQ-036", "AC-02", "SPEC-036")`, and `@traces("REQ-036", "AC-03", "SPEC-036")`.
- Verify targeted `requirement-agent` prompts with existing `REQ`s include `Requirement Decomposition Contract` and `### Existing Requirements Catalog`, empty/targetless prompts omit the catalog, and `review-agent` prompts check capability atomicity and good/edge/failure ACs.
