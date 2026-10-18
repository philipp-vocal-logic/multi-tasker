---
id: TASK-064
title: Implement Per-Role Stage Telemetry, Suitability Summary, and mt run --evaluate
type: implementation
status: done
traces_to:
- REQ-022
- SPEC-022
depends_on:
- TASK-063
required_files:
- tests/test_stage_runner.py
- tests/test_interaction_logging.py
- src/orchestrator/interaction_logger.py
- src/orchestrator/lifecycle.py
- src/orchestrator/stage_runner.py
- src/cli/main.py
write_files:
- src/orchestrator/interaction_logger.py
- src/orchestrator/lifecycle.py
- src/orchestrator/stage_runner.py
- src/cli/main.py
verification_cmd: pytest -q tests/test_stage_runner.py tests/test_interaction_logging.py
---
## Objective
Implement `agent_role` propagation in `record_task_event`, `summarize_pipeline_suitability`, `bootstrap_evaluation_repository`, and `mt run --evaluate`.

## Scoped Instructions
- In `src/orchestrator/interaction_logger.py`, add `agent_role: str = "worker-agent"` to `record_task_event` and add `summarize_pipeline_suitability`.
- In `src/orchestrator/stage_runner.py`, pass `agent_role` to `record_task_event` in `_run_stage_subprocess` and `run_agent_stage`.
- In `src/orchestrator/lifecycle.py`, add `bootstrap_evaluation_repository` to initialize a Git repo, configure `intent_to_requirement` `approval_gate: "auto"`, disable external linters when `ruff`/`mypy` are not target-configured, seed `INT-001`, and commit the baseline repo.
- In `src/cli/main.py`, add `--evaluate` to `mt run` and output the JSON suitability summary.
