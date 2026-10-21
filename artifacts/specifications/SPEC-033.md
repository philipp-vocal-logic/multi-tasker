---
id: SPEC-033
title: Compact Frontmatter Templates, Layer Import Topology, and Role-Tailored Prompts
  Specification
status: approved
traces_to:
- REQ-033
covers_criteria:
- REQ-033:AC-01
- REQ-033:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
---
## Design Overview
Update `src/multi_tasker/orchestrator/prompt_builder.py` so `_render_artifact_schema_block` emits a compact `markdown` frontmatter (`---`) and `## Section` skeleton derived from `policy/schemas.yaml` (`required`, `properties`, `required_sections`) plus `_render_section_budgets`, and replaces the full `ESC` YAML dump with a 3-line `_render_escalation_contract` block. Update `_render_architecture_layers` to include `allowed_internal_imports`, tailor `_build_execution_steps` Step 1 and `_render_code_and_glossary_section` to the active `agent_role`, collapse redundant `Canonical Terms` in `_render_glossary_constraints`, and inline existing `target_files` (`tests` and `implementation`) in `_render_target_context_section` when `target_document` is a `SPEC`.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]`

## Test Contract Mapping
- `REQ-033:AC-01` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
- `REQ-033:AC-02` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
