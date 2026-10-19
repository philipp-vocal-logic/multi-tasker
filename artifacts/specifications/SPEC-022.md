---
id: SPEC-022
title: Per-Role Stage Telemetry and Greenfield Pipeline Suitability Evaluation Specification
status: approved
traces_to:
- REQ-022
covers_criteria:
- REQ-022:AC-01
- REQ-022:AC-02
decisions: []
target_files:
  tests:
  - tests/test_stage_runner.py
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/interaction_logger.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/cli/main.py
---
## Design Overview
Extend `record_task_event` in `src/multi_tasker/orchestrator/interaction_logger.py` with `agent_role: str = "worker-agent"` and pass `agent_role` from `_run_stage_subprocess` and `run_agent_stage` in `src/multi_tasker/orchestrator/stage_runner.py`. Add `summarize_pipeline_suitability` in `src/multi_tasker/orchestrator/interaction_logger.py` to compute `MergeGate` pass rates and per-role invocation counts and latencies from `.report/logs/events.jsonl`. Add `bootstrap_evaluation_repository` in `src/multi_tasker/orchestrator/lifecycle.py` and `--evaluate` on `mt run` in `src/multi_tasker/cli/main.py` to initialize a clean Git repository, seed and commit `INT-001`, run the declarative pipeline, validate `mt check all`, and print the JSON suitability summary.

## Public Interfaces
- `src/multi_tasker/orchestrator/interaction_logger.py`:
  - `record_task_event(repository_root: Path, task_id: str, event_type: str, details: dict[str, Any], execution_context: tuple[str | None, str, str] | None = None, agent_role: str = "worker-agent") -> Path`
  - `summarize_pipeline_suitability(repository_root: Path, completed_ids: list[str] | None = None, passed: bool = True) -> dict[str, Any]`
- `src/multi_tasker/orchestrator/lifecycle.py`:
  - `bootstrap_evaluation_repository(repository_root: Path, intent_text: str) -> str`
- `src/multi_tasker/cli/main.py`:
  - `mt run --evaluate "<intent>"` executes end-to-end suitability evaluation and prints JSON summary.

## Test Contract Mapping
- `REQ-022:AC-01` $\rightarrow$ `tests/test_interaction_logging.py::test_pipeline_suitability_evaluation_and_per_role_telemetry`
- `REQ-022:AC-02` $\rightarrow$ `tests/test_interaction_logging.py::test_pipeline_suitability_evaluation_and_per_role_telemetry`
