---
id: TASK-059
title: Implement Intent What-and-Why Guidance in CLI Parser and External Agents Guide
type: implementation
status: done
traces_to:
- REQ-020
- SPEC-020
depends_on:
- TASK-058
required_files:
- tests/test_interaction_logging.py
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/documentation_generator.py
write_files:
- src/multi_tasker/cli/main.py
- src/multi_tasker/orchestrator/documentation_generator.py
verification_cmd: pytest -q tests/test_interaction_logging.py
---
## Objective
Update `_add_lifecycle_parsers` in `src/multi_tasker/cli/main.py` and `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to prompt for `<what to change and why>` when authoring an `Intent`.

## Scoped Instructions
In `src/multi_tasker/cli/main.py`, update `_add_lifecycle_parsers` so the `intent` subparser registers positional argument `"text"` with `help="Intent statement describing what to change and why (or file path)."`. In `src/multi_tasker/orchestrator/documentation_generator.py`, update `generate_external_agents_guide` step 1 under `## 2. Mandatory Artifact Lifecycle Workflow` to ``"1. `mt intent '<what to change and why>'` -> `artifacts/intents/INT-NNN.md`."``.
