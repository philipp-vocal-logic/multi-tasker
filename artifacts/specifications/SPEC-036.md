---
id: SPEC-036
title: Atomic Requirement Decomposition Contract and Existing Catalog Specification
status: approved
traces_to:
- REQ-036
covers_criteria:
- REQ-036:AC-01
- REQ-036:AC-02
- REQ-036:AC-03
decisions: []
target_files:
  tests:
  - tests/test_orchestrator.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
In `prompt_context.py`, add `render_decomposition_contract` to emit role-specific decomposition rules for `requirement-agent` (one cohesive capability per `REQ`, evaluated across good, edge, and failure `AcceptanceCriteria`) and `planner-agent`, and add `_render_existing_requirements_catalog` in `render_target_context_section` when `target_document` is an `Intent` and `REQ` artifacts exist. Update `ReviewAgent`'s `Semantic Review Rubric` to require capability atomicity and good/edge/failure `AcceptanceCriterion` coverage, and delegate decomposition hint rendering from `prompt_builder.py` so `prompt_builder.py` stays below `refactor_target_file_lines`.

## Public Interfaces
```python
def render_decomposition_contract(
    agent_role: str, next_id: str | None
) -> list[str]:
    """Render Requirement or Planner decomposition contract for agent_role."""


def render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write/target files."""
```

## Test Contract Mapping
- `REQ-036:AC-01`: `tests/test_orchestrator.py::test_atomic_requirement_decomposition_prompt_and_catalog` verifies targeted `requirement-agent` prompts include `Requirement Decomposition Contract` (good/edge/failure `AcceptanceCriteria`) and `### Existing Requirements Catalog`.
- `REQ-036:AC-02`: `tests/test_orchestrator.py::test_atomic_requirement_decomposition_prompt_and_catalog` verifies targetless or empty-repo `requirement-agent` prompts use `REQ-NNN` and omit `Existing Requirements Catalog`.
- `REQ-036:AC-03`: `tests/test_orchestrator.py::test_atomic_requirement_decomposition_prompt_and_catalog` verifies `review-agent` prompts include capability atomicity and good/edge/failure `AcceptanceCriterion` checks in `Semantic Review Rubric`.
