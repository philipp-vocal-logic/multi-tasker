---
id: SPEC-028
title: Canonical Self-Contained Role Prompts and Context Mode Removal Specification
status: approved
traces_to:
- REQ-028
covers_criteria:
- REQ-028:AC-01
- REQ-028:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Remove `default_context_mode` from `policy/permissions.yaml`, `context_mode` from `policy/schemas.yaml`, and `--context-mode` / `resolve_context_mode` / `MT_CONTEXT_MODE` from `src/multi_tasker/cli/main.py`, `src/multi_tasker/checkers/permissions_checker.py`, `src/multi_tasker/orchestrator/stage_runner.py`, and `src/multi_tasker/orchestrator/prompt_builder.py`. Always synthesize a single self-contained `.mt_prompt.md` in `prompt_builder.py` that includes `Self-Contained Context`, the 3-step `Execution Steps` using `mt check all --agent <role> ...`, and inlined `Architecture Layers` from `policy/architecture.yaml`.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_builder.py`: `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]`
- `src/multi_tasker/orchestrator/prompt_builder.py`: `prepare_worker_invocation(worktree_path: Path, document: ArtifactDocument, prompt_file: Path, execution_context: tuple[str, str, str]) -> tuple[str, dict[str, str]]`

## Test Contract Mapping
- `REQ-028:AC-01` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
- `REQ-028:AC-02` -> `tests/test_interaction_logging.py::test_context_mode_policy_validation_and_precedence`
