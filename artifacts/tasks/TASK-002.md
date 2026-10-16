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
  - src/domain/models.py
  - src/domain/parser.py
  - src/checkers/common.py
verification_cmd: "pytest -q tests/test_checkers.py"
---
## Objective
Implement domain models, Markdown/YAML artifact parser, and shared checker infrastructure in `src/domain/` and `src/checkers/common.py`.

## Scoped Instructions
Ensure full type annotations, descriptive unabbreviated identifiers, and compliance with `policy/*.yaml`.
