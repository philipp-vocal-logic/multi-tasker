---
id: TASK-092
title: Implement Cross-Stage Prompt Alignment and Worker Python Output Contract
type: implementation
status: done
traces_to:
- REQ-035
- SPEC-035
depends_on:
- TASK-091
required_files:
- artifacts/requirements/REQ-035.md
- artifacts/specifications/SPEC-035.md
- tests/test_interaction_logging.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
write_files:
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py -k
  prompt
---
## Objective
Update `prompt_builder.py` and `prompt_context.py` so engineering roles share `Source Limits` and `Clean Code AST Rules`, `WorkerAgent` gets a Python Output Contract, and Section 4 and `Execution Steps` eliminate ambiguities.

## Scoped Instructions
- In `prompt_context.py`, include `_render_worker_limits_and_ast` for all roles except `requirement-agent`, skip `required_files` paths already rendered as `ArtifactDocument` entries, and emit `Status: New file` when a `Write File` does not exist on disk.
- In `prompt_builder.py`, render `### Python Source & TestContract Output Contract` for `worker-agent`, resolve concrete stage output file paths in `_build_execution_steps`, and include `traces_to` and `required_files` in `Planner Decomposition Contract`.
