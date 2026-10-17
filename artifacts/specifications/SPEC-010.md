---
id: SPEC-010
title: Multi-Wave Task Execution, Diagnostic Summaries, and Approval Traceability
  Specification
status: approved
traces_to:
- REQ-010
covers_criteria:
- REQ-010:AC-01
- REQ-010:AC-02
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  implementation:
  - src/orchestrator/task_runner.py
  - src/orchestrator/merge_gate.py
  - src/orchestrator/lifecycle.py
  - src/checkers/traceability_checker.py
---
## Design Overview
Update `run_scheduled_tasks` in `src/orchestrator/task_runner.py` to execute successive conflict-free `Task` waves in a loop until no eligible `Tasks` remain or a wave emits `Findings`. Update `_run_verification_command` in `src/orchestrator/merge_gate.py` to prepend the first `E   ` assertion line to `lines[-1]` when `verification_cmd` fails. Scope `check_traceability` in `src/checkers/traceability_checker.py` by `target_paths` and include `"traceability"` in `approve_artifact` and `resolve_escalation` in `src/orchestrator/lifecycle.py`.

## Public Interfaces
- `src/orchestrator/task_runner.py`:
  - `run_scheduled_tasks(repository_root: Path, max_workers: int = 1, agent_command: str | None = None, model_override: str | None = None, environment_override: str | None = None) -> tuple[list[str], list[Finding]]`
- `src/orchestrator/merge_gate.py`:
  - `evaluate_merge_gate(request: GateRequest) -> GateOutcome`
- `src/orchestrator/lifecycle.py`:
  - `approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]`
  - `resolve_escalation(repository_root: Path, escalation_id: str, resolved_by: str) -> list[Finding]`
- `src/checkers/traceability_checker.py`:
  - `check_traceability(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]`

## Test Contract Mapping
- `REQ-010:AC-01` $\rightarrow$ `tests/test_lifecycle.py:test_multi_wave_run_and_approval_traceability_diagnostics`: Verifies a single `mt run` drains a 2-wave dependent `Task` DAG (`TASK-001` $\rightarrow$ `TASK-002`) in sequence.
- `REQ-010:AC-02` $\rightarrow$ `tests/test_lifecycle.py:test_multi_wave_run_and_approval_traceability_diagnostics` and `tests/test_lifecycle.py:test_run_scheduled_tasks_worktree_execution`: Verifies `GATE_VERIFY_CMD_FAILED` includes `E   ` assertion lines and `mt approve` rejects artifacts with broken `traces_to` references (`TRACE_MISSING_REF`).
