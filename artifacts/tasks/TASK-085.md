---
id: TASK-085
title: TestContracts for Per-Intent Traceability Graphs, Pipeline Diagram, Example Prompts, and Coverage
type: test_contract
status: ready
traces_to:
- REQ-032
- SPEC-032
depends_on: []
required_files: []
write_files:
- tests/test_orchestrator.py
verification_cmd: python3 -m py_compile tests/test_orchestrator.py
---
## Objective
Add `test_specification_report_intent_graphs_pipeline_prompts_and_coverage` in `tests/test_orchestrator.py` decorated with `@traces("REQ-032", "AC-01", "SPEC-032")`, `@traces("REQ-032", "AC-02", "SPEC-032")`, and `@traces("REQ-032", "AC-03", "SPEC-032")`.

## Scoped Instructions
Update `tests/test_orchestrator.py` to verify per-Intent Mermaid subgraphs (`### INT-001`, `### INT-002`, and `### Unlinked Artifacts` fallback), absence of `Verified TestContract Links`, Section 6 (`Declarative Agent Pipeline & Escalation Routing` Mermaid diagram), Section 7 (`Generated Example Agent Instructions` collapsible `<details>` 4-backtick role prompts), and Section 8 (`Test & Code Coverage Report` static metrics and `collect_pytest_line_coverage`).
