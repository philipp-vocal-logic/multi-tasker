---
id: SPEC-027
title: Preconfigured Policy Presets for Repository Initialization Specification
status: approved
traces_to:
- REQ-027
covers_criteria:
- REQ-027:AC-01
- REQ-027:AC-02
decisions: []
target_files:
  tests:
  - tests/test_lifecycle.py
  - tests/test_stage_runner.py
  implementation:
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Add `--preset` (`default="python"`) to the `initialize` CLI parser in `src/multi_tasker/cli/main.py` and `preset: str = "python"` to `initialize_repository` in `src/multi_tasker/orchestrator/lifecycle.py`. When `preset == "python"`, scaffold `policy/architecture.yaml` (if missing) with generic Python layers (`domain` under `src/domain/**` and `src/*.py`, `services` under `src/services/**` and `src/application/**`, `cli` under `src/cli/**`, and `tests` under `tests/**`). When `preset == "multi-tasker"`, copy `multi-tasker`'s own `policy/architecture.yaml`. Reject unknown preset values with `[CLI_INVALID_PRESET]`.

## Public Interfaces
- `src/multi_tasker/orchestrator/lifecycle.py`: `initialize_repository(repository_root: Path, preset: str = "python") -> list[Finding]`
- `src/multi_tasker/cli/main.py`: `mt initialize [--preset python|multi-tasker] [--root <dir>]`

## Test Contract Mapping
- `REQ-027:AC-01` -> `tests/test_lifecycle.py::test_initialize_presets_and_invalid_preset_finding`, `tests/test_stage_runner.py::test_real_git_pipeline_commits_verification_pythonpath_and_rev_traceability`
- `REQ-027:AC-02` -> `tests/test_lifecycle.py::test_initialize_presets_and_invalid_preset_finding`
