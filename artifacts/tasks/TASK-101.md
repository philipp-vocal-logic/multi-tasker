---
id: TASK-101
title: Add TestContracts for Disjoint Intent Subgraphs and Superseded Context
type: test_contract
status: ready
traces_to:
  - REQ-040
  - SPEC-040
depends_on: []
required_files:
  - artifacts/requirements/REQ-040.md
  - artifacts/specifications/SPEC-040.md
write_files:
  - tests/test_lifecycle.py
verification_cmd: python3 -m py_compile tests/test_lifecycle.py
---
## Objective
Add `TestContract` coverage in `tests/test_lifecycle.py` for `REQ-040:AC-01`, `REQ-040:AC-02`, and `REQ-040:AC-03`.

## Scoped Instructions
Add `test_superseded_intent_subgraph_separation_and_inlined_spec_context` in `tests/test_lifecycle.py` decorated with `@traces("REQ-040", "AC-01", "SPEC-040")`, `@traces("REQ-040", "AC-02", "SPEC-040")`, and `@traces("REQ-040", "AC-03", "SPEC-040")`.
