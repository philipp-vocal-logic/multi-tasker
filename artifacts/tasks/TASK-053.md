---
id: TASK-053
title: Implement External AGENTS.md Guide Generator and mt initialize Scaffolding
type: implementation
status: planned
traces_to:
- REQ-017
- SPEC-017
depends_on:
- TASK-052
required_files:
- tests/test_interaction_logging.py
- src/orchestrator/documentation_generator.py
- src/orchestrator/lifecycle.py
write_files:
- src/orchestrator/documentation_generator.py
- src/orchestrator/lifecycle.py
verification_cmd: pytest -q tests/test_interaction_logging.py tests/test_transitions_and_execution.py
---
## Objective
Implement `generate_external_agents_guide` in `src/orchestrator/documentation_generator.py` and scaffold `AGENTS.md` when missing during `initialize_repository` in `src/orchestrator/lifecycle.py`.

## Scoped Instructions
Add `generate_external_agents_guide() -> str` in `src/orchestrator/documentation_generator.py` covering project bootstrapping, `policy/*.yaml` configuration tailoring, `PERM_POLICY_MODIFIED` commit rules, and the canonical `mt` lifecycle (`from multi_tasker.domain.models import traces`). Call `generate_external_agents_guide()` from `_scaffold_default_policies_and_gitignore` in `src/orchestrator/lifecycle.py` when `repository_root / "AGENTS.md"` does not exist.
