---
id: TASK-102
title: Implement Disjoint Intent Subgraphs and Superseded Context Inlining
type: implementation
status: ready
traces_to:
  - REQ-040
  - SPEC-040
depends_on:
  - TASK-101
required_files:
  - tests/test_transitions_and_execution.py
  - artifacts/requirements/REQ-040.md
  - artifacts/specifications/SPEC-040.md
write_files:
  - src/multi_tasker/orchestrator/lineage.py
  - src/multi_tasker/orchestrator/prompt_context.py
verification_cmd: pytest -o pythonpath=src -q tests/test_transitions_and_execution.py -k superseded_intent_subgraph
---
## Objective
Keep `group_artifacts_by_intent` subgraphs disjoint across `supersedes` links in `lineage.py` and inline superseded `Requirement`/`Specification`/`target_files` context in `prompt_context.py`.

## Scoped Instructions
Update `_referenced_artifact_ids` and `_document_matches_target` in `src/multi_tasker/orchestrator/lineage.py`, and add `_collect_superseded_context` to `render_target_context_section` in `src/multi_tasker/orchestrator/prompt_context.py`.
