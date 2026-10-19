---
id: SPEC-030
title: TestContract Decorator Prompt Guidance and Pipeline Worker Environment Specification
status: approved
traces_to:
- REQ-030
covers_criteria:
- REQ-030:AC-01
- REQ-030:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
Update `_assemble_prompt_sections` and `_render_code_and_glossary_section` in `src/multi_tasker/orchestrator/prompt_builder.py` to specify `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` (`from multi_tasker.domain.models import traces`) for `planner-agent` and `worker-agent`. Update `_step_declarative_stage` in `src/multi_tasker/orchestrator/stage_runner.py` to pass `options[2] or "agy"` when invoking `run_scheduled_tasks`.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_builder.py`: `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]`
- `src/multi_tasker/orchestrator/stage_runner.py`: `run_declarative_pipeline(repository_root: Path, options: tuple[str | None, str | None, str | None] = (None, None, None)) -> tuple[list[str], list[Finding]]`

## Test Contract Mapping
- `REQ-030:AC-01` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
- `REQ-030:AC-02` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
