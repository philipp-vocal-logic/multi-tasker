---
id: SPEC-019
title: Aligned Source Sizing Thresholds, Task File Budgets, and Prompt Artifact Limit
  Specification
status: deprecated
traces_to:
- REQ-019
covers_criteria:
- REQ-019:AC-01
- REQ-019:AC-02
decisions: []
target_files:
  tests:
  - tests/test_checkers.py
  implementation:
  - src/multi_tasker/checkers/limits_checker.py
  - src/multi_tasker/orchestrator/prompt_builder.py
---
## Design Overview
Configure `max_function_lines: 50`, `max_function_args: 6`, and updated `LIMIT_FUNC_ARGS` remediation in `policy/limits.yaml`, and align fallback defaults in `src/multi_tasker/checkers/limits_checker.py`. Configure `REQ.max_criterion_words: 45`, `TASK.max_write_files: 4`, and `TASK.max_required_files: 6` (alongside matching `TASK` `json_schema` `maxItems`) in `policy/schemas.yaml`. Update `_render_artifact_schema_block` in `src/multi_tasker/orchestrator/prompt_builder.py` to render top-level scalar limits from `artifacts.<TYPE>` (`max_body_words`, `max_acceptance_criteria`, `max_criterion_words`, `max_write_files`, `max_required_files`, `max_finding_words`, `max_findings_per_record`) and `single_paragraph_only` section rules in synthesized role prompts.

## Public Interfaces
- `src/multi_tasker/checkers/limits_checker.py`:
  - `_check_ast_node_limits(node: ast.AST, relative_path: str, source_configuration: dict[str, Any]) -> list[Finding]` uses default `max_function_lines=50` and `max_function_args=6`.
- `src/multi_tasker/orchestrator/prompt_builder.py`:
  - `_render_artifact_schema_block(artifact_type: str, schemas_policy: dict[str, Any], context_mode: str = "inline") -> list[str]` renders top-level `artifacts.<TYPE>` constraints (`- **Artifact Limit `<key>`**: `<val>``) and appends `, single paragraph only` for sections with `single_paragraph_only: true`.

## Test Contract Mapping
- `REQ-019:AC-01` $\rightarrow$ `tests/test_checkers.py::test_aligned_policy_limits_and_prompt_artifact_constraints`
- `REQ-019:AC-02` $\rightarrow$ `tests/test_checkers.py::test_aligned_policy_limits_and_prompt_artifact_constraints`
