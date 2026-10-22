---
id: SPEC-047
title: Worktree PYTHONPATH Src Precedence and Mtime-Aware Stage Artifact Diff Specification
status: approved
traces_to:
- REQ-047
covers_criteria:
- REQ-047:AC-01
- REQ-047:AC-02
- REQ-047:AC-03
decisions: []
target_files:
  tests:
  - tests/test_pipeline_combinations.py
  implementation:
  - src/multi_tasker/orchestrator/merge_gate.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
---
## Design Overview
In `merge_gate.py`, `prompt_builder.py`, and `stage_runner.py`, format `Worktree` `PYTHONPATH` as `f"{worktree_path / 'src'}{os.pathsep}{worktree_path}"`. In `stage_runner.py`, before invoking a stage agent, touch or record baseline `(mtime_ns, size)` alongside text snapshots (or record a pre-invocation timestamp / inode-mtime map) and in `_detect_stage_changes` treat any locked artifact whose `mtime_ns` changed or whose content differs from `before_snapshot` as modified so `normalize_new_stage_artifacts` restores `before_snapshot` and allocates `REV-002.md` even when Cycle 2 writes byte-identical `REV-001.md` content.

## Public Interfaces
- `src/multi_tasker/orchestrator/merge_gate.py`: `_run_verification_command(worktree_path: Path, command_string: str, timeout_seconds: float = 60.0) -> list[Finding]` sets `PYTHONPATH` to `f"{worktree_path / 'src'}{os.pathsep}{worktree_path}"`.
- `src/multi_tasker/orchestrator/prompt_builder.py`: `prepare_worker_invocation(...)` sets `PYTHONPATH` to `f"{worktree_path / 'src'}{os.pathsep}{worktree_path}"`.
- `src/multi_tasker/orchestrator/stage_runner.py`: `_prepare_stage_invocation(...)` sets `PYTHONPATH` to `f"{worktree_path / 'src'}{os.pathsep}{worktree_path}"`; `_detect_stage_changes(worktree_path: Path, before_snapshot: dict[str, str], target_id: str = "", touched_paths: set[str] | None = None) -> list[str]` merges `touched_paths` (or mtime-updated locked files) with `git_changed` before calling `normalize_new_stage_artifacts`.

## Test Contract Mapping
- `REQ-047:AC-01` -> `tests/test_pipeline_combinations.py::test_worktree_pythonpath_precedence_and_identical_review_retry`
- `REQ-047:AC-02` -> `tests/test_pipeline_combinations.py::test_declarative_pipeline_combinations_matrix` and `tests/test_pipeline_combinations.py::test_worktree_pythonpath_precedence_and_identical_review_retry`
- `REQ-047:AC-03` -> `tests/test_pipeline_combinations.py::test_worktree_pythonpath_precedence_and_identical_review_retry`
