---
id: TASK-086
title: Implement Per-Intent Graphs, Pipeline Diagram, Example Prompts, and Coverage Report
type: implementation
status: ready
traces_to:
- REQ-032
- SPEC-032
depends_on:
- TASK-085
required_files:
- tests/test_orchestrator.py
write_files:
- src/multi_tasker/orchestrator/lineage.py
- src/multi_tasker/orchestrator/documentation_generator.py
verification_cmd: pytest -o pythonpath=src -q tests/test_orchestrator.py tests/test_lifecycle.py
---
## Objective
Implement `group_artifacts_by_intent`, `collect_pytest_line_coverage`, and `render_test_and_coverage_section` in `lineage.py` and update `documentation_generator.py` to render per-Intent subgraphs, the pipeline Mermaid diagram, collapsible example prompts, and the test/coverage report.

## Scoped Instructions
Update `src/multi_tasker/orchestrator/lineage.py` and `src/multi_tasker/orchestrator/documentation_generator.py` so `generate_repository_documentation` satisfies `REQ-032:AC-01`, `REQ-032:AC-02`, and `REQ-032:AC-03` while passing all checks.
