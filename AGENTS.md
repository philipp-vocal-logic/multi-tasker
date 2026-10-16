# AGENTS.md — Development Rules & Principles

## 1. Strict MVP Mindset (KISS & YAGNI)
- **Zero Backward Compatibility or Shims**: Greenfield MVP only. Never add fallback paths, deprecated aliases, wrapper functions, or re-exports. Move refactored symbols cleanly and update callers in lockstep.
- **Single Source of Truth**: `policy/*.yaml` and `artifacts/**` are the sole authoritative specification. Never maintain duplicate static specification or prompt files; generate documentation (`./mt documentation`) and role prompts (`./mt prompt <role>`) deterministically from live repository state.
- **Unabbreviated English Identifiers**: Never use abbreviations in filenames, CLI subcommands, classes, functions, parameters, or variables (e.g., `documentation_generator.py`, `ArtifactDocument`, `relative_path`, `configuration`, `frontmatter`).

## 2. Mandatory Dogfooding & Artifact Lifecycle Workflow
Never edit `src/**`, `tests/**`, or completed (`done`) `TASK-NNN.md` artifacts ad-hoc. Every feature, bugfix, or refinement must progress through the canonical pipeline:
1. **Intent (`INT-NNN`)**: Run `./mt intent "<goal>"` to create an `open` Intent in `artifacts/intents/INT-NNN.md`.
2. **Requirement (`REQ-NNN`)**: Author `artifacts/requirements/REQ-NNN.md` (`status: draft`, `traces_to: [INT-NNN]`) and run `./mt approve REQ-NNN` (transitions `REQ-NNN` to `approved` and `INT-NNN` to `processed`).
3. **Specification (`SPEC-NNN`)**: Author `artifacts/specifications/SPEC-NNN.md` (`status: approved`, `traces_to: [REQ-NNN]`), mapping all `REQ-NNN:AC-XX` criteria and declaring `target_files.tests` and `target_files.implementation`.
4. **Tasks (`TASK-NNN`)**:
   - Create a `type: test_contract` Task (`write_files` under `tests/**` only) with `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` tests.
   - Create `type: implementation` Tasks (`depends_on` the `test_contract` Task, `write_files` under `src/**` only, max 3 files per Task).
5. **Isolated Execution (`./mt run`)**: Execute planned Tasks through the `Worktree` and `MergeGate` via `./mt run` so each Task produces a dedicated, scope-verified `TASK-NNN:` commit.

## 3. Architecture, Sizing Limits & Anti-Loop Rules
- **Zero-Noise Gate (`./mt check all`)**: All policies, artifacts, tests, and Git commits must pass `./mt check all` with exit code `0` and `0 bytes` of output.
- **Layer Boundaries (`policy/architecture.yaml`)**: `domain` $\leftarrow$ `checkers` $\leftarrow$ `orchestrator` $\leftarrow$ `cli` $\leftarrow$ `tests`.
- **Hard Limits (`policy/limits.yaml` & `policy/clean_code.yaml`)**:
  - `max_file_lines: 500`, `max_function_lines: 40`, `max_function_args: 5`, `max_mccabe_complexity: 8`
  - `max_docstring_lines: 3` (`35` words), `max_inline_comment_lines: 2` (`25` words)
- **Decompose, Never Line-Golf (One-Strike Circuit Breaker)**: `mt check clean_code` formats Python files in-place via `ruff format --quiet` before `mt check limits` measures lines. If an edit fails `LIMIT_FILE_LINES`, `LIMIT_FUNC_LINES`, or `CODE_C901` once, stop editing in-place and extract a helper function or module immediately.
