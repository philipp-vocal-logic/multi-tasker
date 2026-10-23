---
id: TASK-136
title: Add Multi-Language Checker, Preset, and E2E Pipeline TestContracts
type: test_contract
status: ready
traces_to:
- REQ-052
- SPEC-052
depends_on: []
required_files:
- tests/test_pipeline_combinations.py
write_files:
- tests/test_multi_language_pipeline.py
verification_cmd: python3 -m py_compile tests/test_multi_language_pipeline.py
---
## Objective
Create `tests/test_multi_language_pipeline.py` with `@traces("REQ-052", ...)` TestContracts covering ANSI C and Rust checkers, presets, prompts, and E2E pipeline execution.

## Scoped Instructions
- Add `test_ansi_c_and_rust_checkers_enforce_limits_clean_code_glossary_and_architecture` decorated with `@traces("REQ-052", "AC-01", "SPEC-052")` testing `.c`, `.h`, and `.rs` violations across `clean_code`, `limits`, `glossary`, `architecture`, and `traceability`.
- Add `test_initialize_presets_and_prompt_synthesis_for_ansi_c_and_rust` decorated with `@traces("REQ-052", "AC-02", "SPEC-052")` verifying `mt initialize --preset ansi-c` and `--preset rust` and `mt prompt` code contracts.
- Add `test_end_to_end_pipeline_execution_across_python_ansi_c_and_rust` decorated with `@traces("REQ-052", "AC-03", "SPEC-052")` running `mt run --pipeline` from `INT` to `TASK` with real `pytest`, `gcc -std=c89`, and `rustfmt`/`rustc --test` verification.
