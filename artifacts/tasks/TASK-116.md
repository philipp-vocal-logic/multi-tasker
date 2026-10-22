---
id: TASK-116
title: Implement Pipeline Review Retry, In-Run Escalation Rerouting, and Context Inlining
type: implementation
status: ready
traces_to:
  - REQ-046
  - SPEC-046
depends_on:
  - TASK-115
  - TASK-117
  - TASK-118
required_files:
  - tests/test_pipeline_combinations.py
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
write_files:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/router.py
  - src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_pipeline_combinations.py tests/test_review_gates.py tests/test_stage_runner.py tests/test_stage_escalation.py
---
## Objective
Update `parser.py`, `prompt_context.py`, `router.py`, and `stage_runner.py` to support multi-cycle review retries, in-run `routed_to_agent` escalation dispatch, failed `ReviewRecord` and `ESC` context inlining, and `before_snapshot` restoration.

## Scoped Instructions
- In `src/multi_tasker/domain/parser.py`, restore `before_snapshot` content when `normalize_new_stage_artifacts` renumbers a colliding locked file so append-only `REV` records are preserved.
- In `src/multi_tasker/orchestrator/prompt_context.py`, inline `affected_artifacts`/`target_artifacts` and failed `REV` / rejected draft context in `render_target_context_section`.
- In `src/multi_tasker/orchestrator/router.py` and `src/multi_tasker/orchestrator/stage_runner.py` (keeping all modules <= 400 lines), implement `handle_pipeline_step_outcome` to reset `STAGE_REVIEW_REJECTED` artifacts (`draft`/`blocked`), exclude review-rejected drafts from `covered` in `find_actionable_stage_target`, and continue on `routed_to_agent` `GATE_TASK_ESCALATED`.
