---
id: TASK-135
title: Implement Policy-Driven Gitignore Scaffolding, Lineage Test Glob, and Planner Verification Commands
type: implementation
status: done
traces_to:
- REQ-051
- SPEC-051
depends_on:
- TASK-133
- TASK-134
required_files:
- tests/test_lifecycle.py
- tests/test_orchestrator.py
- tests/test_prompt_builder.py
- src/multi_tasker/checkers/common.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/prompt_builder.py
write_files:
- src/multi_tasker/checkers/common.py
- src/multi_tasker/orchestrator/lifecycle.py
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/prompt_context.py
- src/multi_tasker/orchestrator/prompt_builder.py
verification_cmd: pytest -o pythonpath=src -q tests/test_lifecycle.py tests/test_orchestrator.py
  tests/test_prompt_builder.py
---
## Objective
Update `lifecycle.py`, `lineage.py`, `prompt_context.py`, and `prompt_builder.py` to read `.gitignore` entries, `test_file_glob`, and planner verification commands from `policy/*.yaml`.

## Scoped Instructions
- In `src/multi_tasker/orchestrator/lifecycle.py`, derive `.gitignore` entries from `load_ephemeral_globs(repository_root)` instead of `DEFAULT_GITIGNORE_ENTRIES` and update `bootstrap_evaluation_repository` to set `forbidden_calls_in_src: []` if needed.
- In `src/multi_tasker/orchestrator/lineage.py`, read `test_file_glob` from `policy/traceability.yaml` in `collect_test_trace_links` and `_compute_static_test_metrics`.
- In `src/multi_tasker/orchestrator/prompt_context.py` and `src/multi_tasker/orchestrator/prompt_builder.py`, read `test_contract_verification_cmd` and `implementation_verification_cmd` from `policy/traceability.yaml` in `render_decomposition_contract`.
