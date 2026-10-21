---
id: SPEC-034
title: Non-Fixed Prompt Example IDs, Prompt Line-Length Wrapping, and Glossary Terms Specification
status: approved
traces_to:
- REQ-034
covers_criteria:
- REQ-034:AC-01
- REQ-034:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
Extract target context and vocabulary rendering helpers from `src/multi_tasker/orchestrator/prompt_builder.py` into `src/multi_tasker/orchestrator/prompt_context.py`. Update `prompt_builder.py` so `_format_property_hint` emits non-fixed `id: <TYPE>-NNN` and `AC-XX` placeholders in schema skeletons, `_render_escalation_contract` emits `id: ESC-NNN` instead of `id: ESC-001`, and `_assemble_prompt_sections` uses `f"{primary_type}-NNN"` when `target_doc is None` while preserving sequential `next_artifact_id` for targeted runs. Add `MAX_PROMPT_LINE_LENGTH = 88` and `wrap_prompt_lines` in `prompt_context.py` so synthesized prompt instruction lines (Sections 1 to 3) wrap within 88 characters, include `max_line_length=88` in `WorkerAgent` `Source Limits`, and render `- **Glossary Terms**:` (`canonical` and `code_identifiers`) alongside `- **Forbidden Synonyms**:`.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_context.py`:
  - `MAX_PROMPT_LINE_LENGTH: int = 88`
  - `wrap_prompt_lines(lines: list[str]) -> list[str]`
  - `render_code_and_glossary_section(repository_root: Path, agent_role: str) -> list[str]`
  - `render_target_context_section(repository_root: Path, target_document: ArtifactDocument, by_identifier: dict[str, ArtifactDocument]) -> list[str]`
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]`

## Test Contract Mapping
- `REQ-034:AC-01` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
- `REQ-034:AC-02` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
