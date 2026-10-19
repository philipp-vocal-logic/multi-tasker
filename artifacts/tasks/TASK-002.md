---
id: TASK-002
title: Implement Domain Models, Parser, and Common Checker Utilities for SPEC-001
type: implementation
status: done
traces_to: [REQ-001, SPEC-001]
depends_on: [TASK-001]
required_files:
  - tests/test_checkers.py
write_files:
  - src/multi_tasker/domain/models.py
  - src/multi_tasker/domain/parser.py
  - src/multi_tasker/checkers/common.py
verification_cmd: "pytest -q tests/test_checkers.py"
---
## Objective
Implement domain models, Markdown/YAML artifact parser, and shared checker infrastructure in `src/multi_tasker/domain/` and `src/multi_tasker/checkers/common.py`.

## Scoped Instructions
Ensure full type annotations, descriptive unabbreviated identifiers, and compliance with `policy/*.yaml`.
