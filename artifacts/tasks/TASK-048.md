---
id: TASK-048
title: Implement Default Policy and Gitignore Scaffolding and Worktree PYTHONPATH Ordering
type: implementation
status: planned
traces_to:
- REQ-016
- SPEC-016
depends_on:
- TASK-047
required_files:
- tests/test_lifecycle.py
- src/orchestrator/lifecycle.py
- src/orchestrator/prompt_builder.py
- src/orchestrator/stage_runner.py
write_files:
- src/orchestrator/lifecycle.py
- src/orchestrator/prompt_builder.py
- src/orchestrator/stage_runner.py
verification_cmd: pytest -q tests/test_lifecycle.py tests/test_stage_runner.py
---
## Objective
Scaffold missing default `policy/*.yaml` templates and `.gitignore` entries in `src/orchestrator/lifecycle.py`, and prepend `worktree_path` to `PYTHONPATH` in `src/orchestrator/prompt_builder.py` and `src/orchestrator/stage_runner.py`.

## Scoped Instructions
Implement `_scaffold_default_policies_and_gitignore` in `src/orchestrator/lifecycle.py` and invoke it from `initialize_repository` so missing `policy/*.yaml` files and `.gitignore` entries (`.worktrees/`, `.report/`, `.mt_prompt.md`) are created without overwriting existing files. Update `prepare_worker_invocation` in `src/orchestrator/prompt_builder.py` and `_prepare_stage_invocation` in `src/orchestrator/stage_runner.py` so `PYTHONPATH` begins with `str(worktree_path)`.
