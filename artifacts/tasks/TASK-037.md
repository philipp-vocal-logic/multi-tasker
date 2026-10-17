---
id: TASK-037
title: Implement Per-Agent Policy Validation and Four-Tier Model Resolution
type: implementation
status: done
traces_to:
- REQ-013
- SPEC-013
depends_on:
- TASK-036
required_files:
- tests/test_stage_runner.py
write_files:
- src/checkers/permissions_checker.py
- src/orchestrator/prompt_builder.py
verification_cmd: pytest -q tests/test_checkers.py
---
## Objective
Validate per-agent `model` and `worktree_execution` in `src/checkers/permissions_checker.py` and resolve 4-tier role models in `src/orchestrator/prompt_builder.py`.

## Scoped Instructions
Update `_validate_execution_environments` in `src/checkers/permissions_checker.py` to validate `model` and `worktree_execution` on each entry in `agents`. Update `_render_permissions_section` and `resolve_task_execution` in `src/orchestrator/prompt_builder.py` to display and resolve `agents.<role>.model` (`gemini-4-argon` for high-capability agents) with `CLI > Artifact > Agent Role > Global` precedence.
