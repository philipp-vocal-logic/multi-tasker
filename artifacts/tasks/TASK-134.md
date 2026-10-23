---
id: TASK-134
title: Implement Policy-Driven Extensions, Ephemeral Globs, Forbidden Calls, and Test Globs
type: implementation
status: done
traces_to:
- REQ-051
- SPEC-051
depends_on:
- TASK-133
required_files:
- tests/test_clean_code_checker.py
- tests/test_lifecycle.py
- src/multi_tasker/checkers/common.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/glossary_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
write_files:
- src/multi_tasker/checkers/common.py
- src/multi_tasker/checkers/architecture_checker.py
- src/multi_tasker/checkers/clean_code_checker.py
- src/multi_tasker/checkers/limits_checker.py
- src/multi_tasker/checkers/glossary_checker.py
- src/multi_tasker/checkers/code_and_git_traceability.py
verification_cmd: pytest -o pythonpath=src -q tests/test_clean_code_checker.py tests/test_checkers.py
  tests/test_architecture_checker.py tests/test_traceability_checker.py
---
## Objective
Extract hardcoded ephemeral paths, `{".py"}` source extensions, `"print"` call checks, and `"test_*.py"` globs in `src/multi_tasker/checkers/**` to read from `policy/*.yaml`.

## Scoped Instructions
- In `src/multi_tasker/checkers/common.py`, add `load_ephemeral_globs(repository_root)` reading `clean_repo_invariants.ignored_ephemeral_globs` from `policy/agent_execution.yaml` and `load_source_extensions(repository_root)` reading `language` and `source_extensions` from `policy/code_quality.yaml`.
- Update `architecture_checker.py`, `clean_code_checker.py`, `limits_checker.py`, `glossary_checker.py`, and `code_and_git_traceability.py` to use `load_source_extensions(repository_root)`.
- In `clean_code_checker.py`, check `ast_rules.forbidden_calls_in_src` instead of `forbid_print_in_src`, and in `code_and_git_traceability.py`, read `test_file_glob` from `policy/traceability.yaml`.
