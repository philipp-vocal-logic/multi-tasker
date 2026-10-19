---
id: SPEC-017
title: External Project AGENTS.md Bootstrapping and Policy Configuration Guide Specification
status: approved
traces_to:
- REQ-017
covers_criteria:
- REQ-017:AC-01
decisions: []
target_files:
  tests:
  - tests/test_interaction_logging.py
  implementation:
  - src/multi_tasker/orchestrator/documentation_generator.py
  - src/multi_tasker/orchestrator/lifecycle.py
---
## Design Overview
Add `generate_external_agents_guide() -> str` in `src/multi_tasker/orchestrator/documentation_generator.py` to synthesize an external project `AGENTS.md` containing one-time bootstrapping steps, `policy/*.yaml` customization instructions (`architecture.yaml`, `glossary.yaml`, `pipeline.yaml`, `permissions.yaml`, `clean_code.yaml`, `limits.yaml`, `schemas.yaml`), the `PERM_POLICY_MODIFIED` commit requirement, and the canonical `mt` lifecycle (`from multi_tasker.domain.models import traces`). Wire `_scaffold_default_policies_and_gitignore` in `src/multi_tasker/orchestrator/lifecycle.py` to write `repository_root / "AGENTS.md"` when missing.

## Public Interfaces
- `src/multi_tasker/orchestrator/documentation_generator.py`:
  - `generate_external_agents_guide() -> str`
- `src/multi_tasker/orchestrator/lifecycle.py`:
  - `_scaffold_default_policies_and_gitignore(repository_root: Path) -> None` writes `AGENTS.md` if not present

## Test Contract Mapping
- `REQ-017:AC-01` $\rightarrow$ `tests/test_interaction_logging.py::test_initialize_scaffolds_default_policies_and_gitignore`
