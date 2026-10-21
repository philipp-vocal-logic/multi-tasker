---
id: SPEC-035
title: Cross-Stage Role Prompt Alignment and Worker Python Output Contract Specification
status: approved
traces_to:
- REQ-035
covers_criteria:
- REQ-035:AC-01
- REQ-035:AC-02
- REQ-035:AC-03
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
In `prompt_context.py`, include `_render_worker_limits_and_ast` for all roles except `requirement-agent` so `SpecificationAgent`, `PlannerAgent`, `WorkerAgent`, and `ReviewAgent` share `Source Limits` and `Clean Code AST Rules`. Add a Python Source and `TestContract` Output Contract block for `WorkerAgent` in `prompt_builder.py`, resolve concrete stage output paths in `_build_execution_steps`, include `traces_to` and `required_files` in `Planner Decomposition Contract`, skip duplicate `required_files` in `render_target_context_section`, and label missing `Write File` paths as new files to create.

## Public Interfaces
```python
def render_code_and_glossary_section(
    repository_root: Path, agent_role: str
) -> list[str]:
    """Render architecture layers, sizing limits, AST rules, and glossary terms."""


def render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write/target files."""
```

## Test Contract Mapping
- `REQ-035:AC-01`: `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes` verifies `Source Limits` and `Clean Code AST Rules` appear in `specification-agent`, `planner-agent`, `worker-agent`, and `review-agent` prompts.
- `REQ-035:AC-02`: `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes` verifies `worker-agent` prompts render `### Python Source & TestContract Output Contract` with `@traces` and docstring/import guidance.
- `REQ-035:AC-03`: `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes` verifies concrete stage verification paths, `required_files` deduplication, and `Status: New file` for non-existent `Write File` targets.
