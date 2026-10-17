---
id: SPEC-012
title: Configurable Orchestrator Context Delivery Mode Specification
status: approved
traces_to:
- REQ-012
covers_criteria:
- REQ-012:AC-01
- REQ-012:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/checkers/permissions_checker.py
  - src/orchestrator/prompt_builder.py
  - src/orchestrator/task_runner.py
  - src/cli/main.py
---
## Design Overview
Extend `_validate_execution_environments` in `src/checkers/permissions_checker.py` to validate `default_context_mode` (`inline` or `paths`) in `policy/permissions.yaml`. Add `resolve_context_mode` and `prepare_worker_invocation` in `src/orchestrator/prompt_builder.py` and extend `build_agent_prompt` with `context_mode` so `inline` embeds full schemas, `forbidden_synonyms`, upstream artifacts, and existing `required_files`/`write_files` contents while `paths` emits concise path pointers. Wire `--context-mode` into `mt prompt` and `mt run` in `src/cli/main.py` and `src/orchestrator/task_runner.py`, setting `MT_CONTEXT_MODE` and expanding `{context_mode}` in `Worktree` executions.

## Public Interfaces
- `src/orchestrator/prompt_builder.py`:
  - `resolve_context_mode(repository_root: Path, document: ArtifactDocument | None = None, context_mode_override: str | None = None) -> str`
  - `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None, context_mode: str | None = None) -> tuple[str, list[Finding]]`
  - `prepare_worker_invocation(worktree_path: Path, document: ArtifactDocument, prompt_file: Path, execution_context: tuple[str, str, str], context_mode_override: str | None = None) -> tuple[str, dict[str, str]]`

## Test Contract Mapping
- `REQ-012:AC-01` $\rightarrow$ `tests/test_interaction_logging.py:test_context_mode_policy_validation_and_precedence`: Verifies `check_permissions` validates `default_context_mode` in `policy/permissions.yaml` and `resolve_context_mode` resolves `CLI > Task > Policy` precedence.
- `REQ-012:AC-02` $\rightarrow$ `tests/test_interaction_logging.py:test_prompt_and_worktree_run_context_modes`: Verifies `mt prompt` and `mt run` with `--context-mode inline` vs `paths` synthesize self-contained or path-referenced prompts and export `MT_CONTEXT_MODE` inside `Worktrees`.
