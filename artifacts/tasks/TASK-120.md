---
id: TASK-120
title: Implement Worktree Src PYTHONPATH Precedence and Sentinel Mtime Stage Diff
  Detection
type: implementation
status: done
traces_to:
- REQ-047
- SPEC-047
depends_on:
- TASK-119
- TASK-121
required_files:
- tests/test_pipeline_combinations.py
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
write_files:
- src/multi_tasker/orchestrator/merge_gate.py
- src/multi_tasker/orchestrator/prompt_builder.py
- src/multi_tasker/orchestrator/stage_runner.py
verification_cmd: pytest -o pythonpath=src -q tests/test_pipeline_combinations.py
  tests/test_review_gates.py tests/test_stage_runner.py tests/test_stage_escalation.py
---
## Objective
Prepend `<worktree_path>/src` to `PYTHONPATH` in `merge_gate.py`, `prompt_builder.py`, and `stage_runner.py`, and detect byte-identical overwrites of locked `REV`/`ESC` stage artifacts via sentinel modification timestamps in `stage_runner.py`.

## Scoped Instructions
- In `merge_gate.py`, `prompt_builder.py`, and `stage_runner.py`, set `PYTHONPATH` to `f"{worktree_path / 'src'}{os.pathsep}{worktree_path}"`.
- In `stage_runner.py`, mark existing `REV-*.md` and `ESC-*.md` files with sentinel timestamp `_SNAPSHOT_MTIME_NS` in `_snapshot_artifacts` and include any `REV-*.md`/`ESC-*.md` whose `st_mtime_ns != _SNAPSHOT_MTIME_NS` in `_detect_stage_changes`.
