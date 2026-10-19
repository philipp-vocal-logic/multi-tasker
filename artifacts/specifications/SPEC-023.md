---
id: SPEC-023
title: Programmatic Artifact ID Normalization and Pipeline Streamlining Specification
status: approved
traces_to:
- REQ-023
covers_criteria:
- REQ-023:AC-01
- REQ-023:AC-02
decisions: []
target_files:
  tests:
  - tests/test_checkers.py
  implementation:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/checkers/code_and_git_traceability.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Add `next_artifact_id` and `normalize_new_stage_artifacts` in `src/multi_tasker/domain/parser.py` so the `Orchestrator` computes sequential `Artifact` identifiers, injects assigned IDs and stage verification/decomposition instructions in `build_agent_prompt`, and renumbers colliding or placeholder stage `Artifacts` (and intra-batch `depends_on`/`traces_to` links) in `run_agent_stage` prior to `MergeGate` evaluation. Update `check_test_contract_coverage` to defer `TRACE_MISSING_TEST_CONTRACT` while `TestContract` `Tasks` are `planned` or `ready`, and handle `subprocess.TimeoutExpired` and single-pass stage review gates in `stage_runner.py` and `lifecycle.py`.

## Public Interfaces
- `next_artifact_id(repository_root: Path, artifact_type: str) -> str`
- `normalize_new_stage_artifacts(worktree_path: Path, existing_ids: set[str], changed_files: list[str]) -> list[str]`

## Test Contract Mapping
- `REQ-023:AC-01` -> `tests/test_checkers.py::test_programmatic_id_normalization_and_streamlined_pipeline_checks`
- `REQ-023:AC-02` -> `tests/test_checkers.py::test_programmatic_id_normalization_and_streamlined_pipeline_checks`
