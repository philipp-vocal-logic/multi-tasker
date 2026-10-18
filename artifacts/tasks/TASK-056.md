---
id: TASK-056
title: Add TestContract for Aligned Policy Limits and Prompt Artifact Limit Rendering
type: test_contract
status: done
traces_to:
- REQ-019
- SPEC-019
depends_on: []
required_files:
- tests/test_checkers.py
- src/orchestrator/prompt_builder.py
write_files:
- tests/test_checkers.py
verification_cmd: pytest -q tests/test_lifecycle.py
---
## Objective
Add `test_aligned_policy_limits_and_prompt_artifact_constraints` in `tests/test_checkers.py` decorated with `@traces("REQ-019", "AC-01", "SPEC-019")` and `@traces("REQ-019", "AC-02", "SPEC-019")` to verify the aligned policy limits and role prompt artifact constraint rendering.

## Scoped Instructions
In `tests/test_checkers.py`, add `test_aligned_policy_limits_and_prompt_artifact_constraints(tmp_path: Path) -> None` decorated with `@traces("REQ-019", "AC-01", "SPEC-019")` and `@traces("REQ-019", "AC-02", "SPEC-019")`. Assert that `policy/limits.yaml` defines `max_function_lines == 50` and `max_function_args == 6`, and `policy/schemas.yaml` defines `REQ.max_criterion_words == 45`, `TASK.max_write_files == 4`, and `TASK.max_required_files == 6` (with matching `TASK` `json_schema` `maxItems`). Also assert that `build_agent_prompt` for `requirement-agent` and `planner-agent` includes `- **Artifact Limit \`max_criterion_words\`**: \`45\``, `- **Artifact Limit \`max_write_files\`**: \`4\``, `- **Artifact Limit \`max_required_files\`**: \`6\``, and `, single paragraph only` on the `ESC` `Blocking Problem` section.
