---
id: SPEC-032
title: Per-Intent Traceability Graphs, Pipeline Diagram, Example Prompts, and Coverage
  Report Specification
status: approved
traces_to:
- REQ-032
covers_criteria:
- REQ-032:AC-01
- REQ-032:AC-02
- REQ-032:AC-03
decisions: []
target_files:
  tests:
  - tests/test_orchestrator.py
  implementation:
  - src/multi_tasker/orchestrator/documentation_generator.py
  - src/multi_tasker/orchestrator/lineage.py
---
## Design Overview
Add `group_artifacts_by_intent`, `collect_pytest_line_coverage`, and `render_test_and_coverage_section` to `src/multi_tasker/orchestrator/lineage.py`. Update `src/multi_tasker/orchestrator/documentation_generator.py` so Section 5 (`Live Repository Traceability Graph`) emits a separate `flowchart TD` per `INT-NNN` (plus an `Unlinked Artifacts` fallback) and omits `Verified TestContract Links`. Append Section 6 (`Declarative Agent Pipeline & Escalation Routing` Mermaid diagram from `policy/pipeline.yaml`), Section 7 (`Generated Example Agent Instructions` collapsible `<details>` blocks with 4-backtick role prompts via `build_agent_prompt`), and Section 8 (`Test & Code Coverage Report` combining static AST/AcceptanceCriterion metrics and cached `sys.monitoring` per-module line coverage).

## Public Interfaces
- `src/multi_tasker/orchestrator/lineage.py`:
  - `group_artifacts_by_intent(by_identifier: dict[str, ArtifactDocument]) -> list[tuple[str, dict[str, ArtifactDocument]]]`
  - `collect_pytest_line_coverage(repository_root: Path) -> dict[str, Any]`
  - `render_test_and_coverage_section(repository_root: Path) -> list[str]`
- `src/multi_tasker/orchestrator/documentation_generator.py`:
  - `generate_repository_documentation(repository_root: Path) -> str`
  - `write_repository_documentation(repository_root: Path) -> Path`

## Test Contract Mapping
- `REQ-032:AC-01` -> `tests/test_orchestrator.py::test_specification_report_intent_graphs_pipeline_prompts_and_coverage`
- `REQ-032:AC-02` -> `tests/test_orchestrator.py::test_specification_report_intent_graphs_pipeline_prompts_and_coverage`
- `REQ-032:AC-03` -> `tests/test_orchestrator.py::test_specification_report_intent_graphs_pipeline_prompts_and_coverage`
