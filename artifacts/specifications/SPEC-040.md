---
id: SPEC-040
title: Disjoint Intent Subgraphs and Superseded Context Specification
status: approved
traces_to:
- REQ-040
covers_criteria:
- REQ-040:AC-01
- REQ-040:AC-02
- REQ-040:AC-03
decisions: []
target_files:
  tests:
  - tests/test_transitions_and_execution.py
  implementation:
  - src/multi_tasker/orchestrator/lineage.py
  - src/multi_tasker/orchestrator/prompt_context.py
---
## Design Overview
Keep `"supersedes"` out of `_referenced_artifact_ids` in `src/multi_tasker/orchestrator/lineage.py` so `_expand_intent_subgraph` partitions `INT-001` and `INT-002` into disjoint Mermaid subgraphs, while checking `supersedes` in `_document_matches_target` so `trace_lineage` continues expanding across superseded `Requirement` artifacts. Add `_collect_superseded_context` in `src/multi_tasker/orchestrator/prompt_context.py` and invoke it in `render_target_context_section` so `specification-agent` prompts targeting a superseding `Requirement` inline the superseded `Requirement`, its `Specification`, and existing `target_files`.

## Public Interfaces
```python
# src/multi_tasker/orchestrator/prompt_context.py
def _collect_superseded_context(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> tuple[list[ArtifactDocument], list[str]]: ...
```

## Test Contract Mapping
- `REQ-040:AC-01` -> `tests/test_transitions_and_execution.py::test_superseded_intent_subgraph_separation_and_inlined_spec_context`
- `REQ-040:AC-02` -> `tests/test_transitions_and_execution.py::test_superseded_intent_subgraph_separation_and_inlined_spec_context`
- `REQ-040:AC-03` -> `tests/test_transitions_and_execution.py::test_superseded_intent_subgraph_separation_and_inlined_spec_context`
