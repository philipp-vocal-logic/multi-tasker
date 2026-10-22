---
id: TASK-122
title: Align Worktree PYTHONPATH Assertion in Interaction Logging TestContract
type: test_contract
status: done
traces_to:
- REQ-047
- SPEC-047
depends_on:
- TASK-120
required_files:
- artifacts/requirements/REQ-047.md
- artifacts/specifications/SPEC-047.md
- tests/test_interaction_logging.py
write_files:
- tests/test_interaction_logging.py
verification_cmd: pytest -o pythonpath=src -q tests/test_interaction_logging.py
---
## Objective
Update `test_architecture_custom_package_and_worktree_pythonpath` in `tests/test_interaction_logging.py` to assert the `<worktree_path>/src` + `<worktree_path>` `PYTHONPATH` layout defined by `REQ-047:AC-01` and `REQ-026:AC-02`.

## Scoped Instructions
- Update `test_architecture_custom_package_and_worktree_pythonpath` in `tests/test_interaction_logging.py` so `env["PYTHONPATH"]` is checked against `f"{tmp_path / 'src'}:{tmp_path}"` and decorated with `@traces("REQ-047", "AC-01", "SPEC-047")`.
