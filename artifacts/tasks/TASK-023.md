---
id: TASK-023
title: Implement Atomic Approval and Clean Failed Task Execution for SPEC-008
type: implementation
status: done
traces_to:
- REQ-008
- SPEC-008
depends_on:
- TASK-022
required_files:
- tests/test_orchestrator.py
write_files:
- src/orchestrator/lifecycle.py
verification_cmd: pytest -q
---
## Objective
Enforce validate-before-mutate in `approve_artifact` and remove redundant `BaseBranch` `Task` writes on failed `MergeGate` verification in `_finalize_task_outcome`.

## Scoped Instructions
Run `run_checks` before `update_artifact_frontmatter` in `approve_artifact` and remove the failure-path `update_artifact_frontmatter` call on `absolute_task` in `_finalize_task_outcome` in `src/orchestrator/lifecycle.py`.
