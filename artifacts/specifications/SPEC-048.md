---
id: SPEC-048
title: Domain-Separated Policy Configuration Files Specification
status: approved
traces_to:
- REQ-048
covers_criteria:
- REQ-048:AC-01
- REQ-048:AC-02
- REQ-048:AC-03
decisions: []
target_files:
  tests:
  - tests/test_architecture_checker.py
  - tests/test_checkers.py
  - tests/test_clean_code_checker.py
  - tests/test_interaction_logging.py
  - tests/test_lifecycle.py
  - tests/test_orchestrator.py
  - tests/test_pipeline_combinations.py
  - tests/test_review_gates.py
  - tests/test_schemas_checker.py
  - tests/test_stage_runner.py
  - tests/test_task_runner.py
  - tests/test_traceability_checker.py
  implementation:
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/checkers/architecture_checker.py
  - src/multi_tasker/checkers/clean_code_checker.py
  - src/multi_tasker/checkers/limits_checker.py
  - src/multi_tasker/checkers/permissions_checker.py
  - src/multi_tasker/checkers/schemas_checker.py
  - src/multi_tasker/cli/main.py
  - src/multi_tasker/cli/output.py
  - src/multi_tasker/orchestrator/documentation_generator.py
  - src/multi_tasker/orchestrator/lifecycle.py
  - src/multi_tasker/orchestrator/merge_gate.py
  - src/multi_tasker/orchestrator/prompt_builder.py
  - src/multi_tasker/orchestrator/prompt_context.py
  - src/multi_tasker/orchestrator/stage_runner.py
  - src/multi_tasker/orchestrator/worktree.py
---
## Design Overview
Separate `policy/*.yaml` into 10 single-concern files:
- `policy/agent_permissions.yaml`: `global_forbidden_write`, `escalation_exclusivity`, and per-role `read_scope`, `allowed_write`, `escalation_write`.
- `policy/agent_execution.yaml`: `clean_repo_invariants`, `execution_environments`, and per-role `model` and `worktree_execution`.
- `policy/artifact_schemas.yaml`: `schemas` (frontmatter JSON schemas and `path_glob`).
- `policy/artifact_limits.yaml`: `artifacts` (`required_sections`, `sections`, and frontmatter/body word and count limits).
- `policy/artifact_lifecycle.yaml`: `state_transitions`, `execution_bounds`, `stages`, and `escalation_routes`.
- `policy/code_architecture.yaml`, `policy/code_limits.yaml`, `policy/code_quality.yaml`, `policy/glossary.yaml`, and `policy/traceability.yaml`.

Update `domain/parser.py`, all checkers, `Orchestrator` modules, CLI output/main, and `TestContracts` to load the new single-concern policy paths directly.

## Public Interfaces
```python
# src/multi_tasker/domain/parser.py
def load_pipeline_policy(repository_root: Path) -> dict[str, Any]:
    """Load policy/artifact_lifecycle.yaml if present, else return empty dict."""

def load_state_transitions(
    repository_root: Path, fallback_policy: dict[str, Any] | None = None
) -> dict[str, dict[str, set[str]]]:
    """Extract state_transitions table from policy/artifact_lifecycle.yaml."""
```

## Test Contract Mapping
- `REQ-048:AC-01` -> `tests/test_stage_runner.py::test_per_agent_model_precedence_and_policy_validation`
- `REQ-048:AC-02` -> `tests/test_schemas_checker.py::test_aligned_policy_limits_and_prompt_artifact_constraints`
- `REQ-048:AC-03` -> `tests/test_orchestrator.py::test_all_policy_yaml_keys_are_enforced_and_read`
