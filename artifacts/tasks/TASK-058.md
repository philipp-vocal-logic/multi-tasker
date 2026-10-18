---
id: TASK-058
title: Add TestContract for Intent What-and-Why Guidance and RequirementAgent Mission
type: test_contract
status: done
traces_to:
- REQ-020
- SPEC-020
depends_on: []
required_files:
- tests/test_interaction_logging.py
- src/cli/main.py
- src/orchestrator/documentation_generator.py
write_files:
- tests/test_interaction_logging.py
verification_cmd: pytest -q tests/test_lifecycle.py
---
## Objective
Add `test_intent_why_guidance_in_prompt_cli_and_agents_guide` in `tests/test_interaction_logging.py` decorated with `@traces("REQ-020", "AC-01", "SPEC-020")` and `@traces("REQ-020", "AC-02", "SPEC-020")` to verify `Intent` and `RequirementAgent` mission guidance and `mt intent` authoring instructions.

## Scoped Instructions
In `tests/test_interaction_logging.py`, add `test_intent_why_guidance_in_prompt_cli_and_agents_guide() -> None` decorated with `@traces("REQ-020", "AC-01", "SPEC-020")` and `@traces("REQ-020", "AC-02", "SPEC-020")`. Assert that `build_agent_prompt(REPOSITORY_ROOT, "requirement-agent")[0]` contains `"translating its requested change and motivating reason into testable AcceptanceCriteria and ImpactAnalysis"`. Also assert that `generate_external_agents_guide()` contains ``"mt intent '<what to change and why>'"`` and that `build_parser()` formats `intent` subcommand help with `"Intent statement describing what to change and why (or file path)."`.
