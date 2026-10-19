---
id: SPEC-004
title: Role Prompt Synthesis, Subprocess Timeouts, and Commit Scope Specification
status: approved
traces_to: [REQ-004]
covers_criteria:
  - REQ-004:AC-01
  - REQ-004:AC-02
  - REQ-004:AC-03
decisions: []
target_files:
  tests:
    - tests/test_orchestrator.py
    - tests/test_lifecycle.py
    - tests/test_traceability_and_cli.py
  implementation:
    - src/multi_tasker/orchestrator/prompt_builder.py
    - src/multi_tasker/orchestrator/merge_gate.py
    - src/multi_tasker/orchestrator/lifecycle.py
    - src/multi_tasker/checkers/common.py
    - src/multi_tasker/checkers/traceability_checker.py
    - src/multi_tasker/cli/main.py
---
## Design Overview
Implement `src/multi_tasker/orchestrator/prompt_builder.py` (`build_agent_prompt`) and `mt prompt` in `src/multi_tasker/cli/main.py`, enforce subprocess timeouts in `src/multi_tasker/orchestrator/merge_gate.py` and `src/multi_tasker/orchestrator/lifecycle.py`, transition upstream `Intent` status to `processed` in `approve_artifact`, and enforce `Task` commit `WriteScope` and `Intent` coverage in `src/multi_tasker/checkers/traceability_checker.py`.

## Public Interfaces
```python
def build_agent_prompt(repository_root: Path, agent_role: str, target_id: str | None = None) -> tuple[str, list[Finding]]: ...
def get_git_commit_files(repository_root: Path, commit_hash: str) -> list[str]: ...
```

## Test Contract Mapping
- `test_merge_gate_enforces_verification_command_timeout` -> `REQ-004:AC-01`
- `test_role_prompt_synthesis_and_context_assembly` -> `REQ-004:AC-02`
- `test_worktree_run_provides_prompt_file_and_role_env` -> `REQ-004:AC-02`
- `test_git_commit_scope_and_intent_traceability` -> `REQ-004:AC-03`
