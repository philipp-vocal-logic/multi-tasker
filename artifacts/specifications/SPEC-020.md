---
id: SPEC-020
title: Intent What-and-Why Authoring Guidance and RequirementAgent Mission Specification
status: approved
traces_to:
- REQ-020
covers_criteria:
- REQ-020:AC-01
- REQ-020:AC-02
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/orchestrator/documentation_generator.py
---
## Design Overview
Update `Intent` and `RequirementAgent` definitions in `policy/glossary.yaml` so `build_agent_prompt` synthesizes a `RequirementAgent` mission that explicitly translates both the requested change and motivating reason from `INT-NNN` into testable `AcceptanceCriteria` and `ImpactAnalysis`. Update `_add_lifecycle_parsers` in `src/multi_tasker/cli/main.py` and `generate_external_agents_guide` in `src/multi_tasker/orchestrator/documentation_generator.py` to guide users and external agents to pass `<what to change and why>` to `mt intent`.

## Public Interfaces
- `src/multi_tasker/cli/main.py`:
  - `_add_lifecycle_parsers(subparsers: Any) -> None` configures `intent` positional argument `text` with `help="Intent statement describing what to change and why (or file path)."`.
- `src/multi_tasker/orchestrator/documentation_generator.py`:
  - `generate_external_agents_guide() -> str` renders step 1 of the workflow as ``1. `mt intent '<what to change and why>'` -> `artifacts/intents/INT-NNN.md`.``.

## Test Contract Mapping
- `REQ-020:AC-01` $\rightarrow$ `tests/test_interaction_logging.py::test_intent_why_guidance_in_prompt_cli_and_agents_guide`
- `REQ-020:AC-02` $\rightarrow$ `tests/test_interaction_logging.py::test_intent_why_guidance_in_prompt_cli_and_agents_guide`
