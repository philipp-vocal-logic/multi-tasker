---
id: SPEC-013
title: Configurable Per-Agent Worktree Execution and Role Model Selection Specification
status: approved
traces_to:
- REQ-013
covers_criteria:
- REQ-013:AC-01
- REQ-013:AC-02
decisions: []
target_files:
  tests:
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/cli/main.py
---
## Design Overview
Extend `_validate_execution_environments` in `src/multi_tasker/checkers/permissions_checker.py` to validate per-agent `model` (non-empty string) and `worktree_execution` (boolean) in `policy/permissions.yaml`. Update `resolve_task_execution` in `src/multi_tasker/orchestrator/prompt_builder.py` to accept `agent_role: str = "worker-agent"` and resolve model precedence as `CLI > Artifact > Agent Role > Global Default`. Create `src/multi_tasker/orchestrator/stage_runner.py` (`is_worktree_agent_enabled`, `run_agent_stage`) to execute any configured agent role (`requirement-agent`, `specification-agent`, `planner-agent`, `worker-agent`, `review-agent`) in an isolated `Worktree` verified by `MergeGate`, and wire `--agent` and `--target` into `mt run` in `src/multi_tasker/cli/main.py`.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `resolve_task_execution(repository_root: Path, document: ArtifactDocument, options: tuple[str | None, str | None, str | None] = (None, None, None), agent_role: str = "worker-agent") -> tuple[str | None, str, str]`
- `src/multi_tasker/orchestrator/stage_runner.py`:
  - `is_worktree_agent_enabled(repository_root: Path, agent_role: str) -> bool`
  - `run_agent_stage(repository_root: Path, agent_role: str, target_id: str, options: tuple[str | None, str | None, str | None] = (None, None, None)) -> tuple[list[str], list[Finding]]`

## Test Contract Mapping
- `REQ-013:AC-01` $\rightarrow$ `tests/test_stage_runner.py:test_per_agent_model_precedence_and_policy_validation`: Verifies `gemini-4-argon` resolution for high-capability roles (`requirement-agent`, `specification-agent`, `planner-agent`, `review-agent`), `gemini-3.8-flash-high` for `worker-agent`, 4-tier `CLI > Artifact > Agent Role > Global` precedence, and `PERM_INVALID_EXEC_ENV` on invalid agent settings.
- `REQ-013:AC-02` $\rightarrow$ `tests/test_stage_runner.py:test_configurable_worktree_stage_execution_and_toggle`: Verifies `mt run --agent <role> --target <id>` executes enabled roles in isolated `Worktrees` with `gemini-4-argon`, commits valid artifacts after `MergeGate`, and emits `CLI_AGENT_WORKTREE_DISABLED` when `worktree_execution` is `false`.
