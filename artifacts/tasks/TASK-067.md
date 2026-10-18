---
id: TASK-067
title: Wire Stage Artifact Normalization, Timeout Handling, and Streamlined Review
  Gates
type: implementation
status: done
traces_to:
- REQ-023
- SPEC-023
depends_on:
- TASK-065
- TASK-066
required_files:
- artifacts/specifications/SPEC-023.md
- tests/test_checkers.py
- src/domain/parser.py
write_files:
- src/orchestrator/stage_runner.py
- src/orchestrator/lifecycle.py
verification_cmd: pytest -q tests/test_checkers.py tests/test_stage_runner.py tests/test_traceability_and_cli.py
---
## Objective
Update `src/orchestrator/stage_runner.py` and `src/orchestrator/lifecycle.py` to normalize newly created stage `Artifacts` before `MergeGate`, catch `subprocess.TimeoutExpired`, execute `review-agent` once per stage, and configure evaluation repositories for streamlined task generation.

## Scoped Instructions
Keep `src/orchestrator/stage_runner.py` and `src/orchestrator/lifecycle.py` under 400 lines and ensure all unit and integration tests pass.
