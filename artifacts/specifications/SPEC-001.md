---
id: SPEC-001
title: Deterministic Policy Checkers and Zero-Noise CLI Specification
status: approved
traces_to: [REQ-001]
covers_criteria:
  - REQ-001:AC-01
  - REQ-001:AC-02
  - REQ-001:AC-03
  - REQ-001:AC-04
  - REQ-001:AC-05
decisions: []
target_files:
  tests:
    - tests/test_checkers.py
    - tests/test_traceability_and_cli.py
  implementation:
    - src/domain/models.py
    - src/domain/parser.py
    - src/checkers/common.py
    - src/checkers/schemas_checker.py
    - src/checkers/permissions_checker.py
    - src/checkers/glossary_checker.py
    - src/checkers/limits_checker.py
    - src/checkers/clean_code_checker.py
    - src/checkers/architecture_checker.py
    - src/checkers/traceability_checker.py
    - src/checkers/runner.py
    - src/cli/output.py
    - src/cli/main.py
---
## Design Overview
Implement modular checkers in `src/checkers/` backed by shared utilities in `src/checkers/common.py`, domain models in `src/domain/`, and CLI output formatting in `src/cli/output.py` and `src/cli/main.py`.

## Public Interfaces
```python
def check_permissions(repository_root: Path, agent_role: str | None = None, task_id: str | None = None) -> list[Finding]: ...
def check_schemas(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def check_glossary(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def check_limits(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def check_clean_code(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def check_architecture(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def check_traceability(repository_root: Path, target_paths: list[str] | None = None) -> list[Finding]: ...
def run_checks(repository_root: Path, check_names: list[str]) -> list[Finding]: ...
```

## Test Contract Mapping
- `test_permissions_checker_matrix` -> `REQ-001:AC-01`
- `test_parser_and_glossary_branches` -> `REQ-001:AC-02`
- `test_clean_code_checker_violation_branches` -> `REQ-001:AC-03`
- `test_traceability_checker_all_failure_modes` -> `REQ-001:AC-04`
- `test_self_check_passes_with_zero_output` -> `REQ-001:AC-05`
