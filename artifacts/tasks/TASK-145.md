---
id: TASK-145
title: Add Multi-Language Parallel Layers, MergeGate Fault, and Supersession TestContracts
type: test_contract
status: ready
traces_to:
- REQ-055
- SPEC-055
depends_on:
- TASK-144
required_files:
- tests/test_multi_language_scenarios.py
write_files:
- tests/test_multi_language_workflows.py
verification_cmd: python3 -m py_compile tests/test_multi_language_workflows.py
---
## Objective
Create `tests/test_multi_language_workflows.py` with `@traces("REQ-055", "AC-04", "SPEC-055")` E2E tests across Python, ANSI C, and Rust for parallel waves, MergeGate faults, and Requirement supersession.

## Scoped Instructions
- Exercise `--max-workers 2` across `src/domain/*` and `src/services/*`, language-specific `MergeGate` rejections (`CODE_PRINT_FORBIDDEN`, `ARCH_FORBIDDEN_IMPORT`, `PERM_LOCKED_TEST_CONTRACT`), and `INT-002` / `REQ-002` (`supersedes: [REQ-001]`) evolution across all three languages.
