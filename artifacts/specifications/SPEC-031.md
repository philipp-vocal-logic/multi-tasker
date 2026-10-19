---
id: SPEC-031
title: Streamlined Worker and Stage Role Prompt Synthesis Specification
status: approved
traces_to:
- REQ-031
covers_criteria:
- REQ-031:AC-01
- REQ-031:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/prompt_builder.py
---
## Design Overview
Remove `"worker-agent": "TASK"` from `ROLE_TO_OUTPUT_SCHEMA` in `src/multi_tasker/orchestrator/prompt_builder.py` so `worker-agent` prompts do not emit `Assigned Next Artifact ID` or `### TASK Output Contract`. Pass `target_doc` into `_assemble_prompt_sections` and `_render_permissions_section` so `$TASK_WRITE_FILES` expands to the target Task's `write_files` and `Execution Steps` Step 2 renders the exact `mt check all --agent worker-agent --task <id> --paths <write_files> && <verification_cmd>` command. Specify target artifact statuses (`in_review`, `ready`) in Step 1 for artifact roles.

## Public Interfaces
- `src/multi_tasker/orchestrator/prompt_builder.py`: `build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]`

## Test Contract Mapping
- `REQ-031:AC-01` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
- `REQ-031:AC-02` -> `tests/test_interaction_logging.py::test_prompt_and_worktree_run_context_modes`
