# AGENTS.md — Development Rules & Principles

## 1. Strict MVP Mindset — Zero Backward Compatibility, Zero Shims
- **NO Backward Compatibility**: This is a single, greenfield MVP project. Never add backward-compatibility layers, fallback paths, deprecated aliases, or legacy support.
- **NO Shims or Re-exports**: When moving or refactoring a function, class, or CLI command, move it cleanly to its canonical location and update all callers and tests directly. Never leave re-exports, wrapper functions, or compatibility shims behind.
- **Single Canonical Way**: Every CLI command, checker name, function signature, and configuration key must have exactly one canonical representation. If the specification or code changes, update the policy, code, artifacts, and tests in lockstep.
- **Single Source of Truth (No Duplicate Static Specs)**: `policy/*.yaml` and `artifacts/**` are the sole authoritative specification of the system. Never maintain duplicate static prose specification files (such as `SPECIFICATION.md` or `USE_CASE_SPEC.md`); human-readable documentation, use-case tables, and Mermaid diagrams are generated deterministically from the live repository state (`mt documentation`).
- **NO Abbreviations in Filenames, CLI Commands, or Code Identifiers**: Always use full, unambiguous English words for filenames, directories, CLI subcommands, classes, functions, parameters, and local variables (e.g., `documentation_generator.py` instead of `docs_gen.py`, `ArtifactDocument` instead of `ArtifactDoc`, `relative_path` instead of `rel_path`, `configuration` instead of `cfg`, `frontmatter` instead of `fm`). Enforce forbidden abbreviations deterministically via `policy/glossary.yaml` and `policy/clean_code.yaml`.

## 2. Core Engineering Constraints (KISS, YAGNI & Policy Enforcement)
- **CLI-Enforced Policy (`./mt check all`)**: All code, tests, and artifacts must pass `./mt check all` with exit code `0` and `0 bytes` of output.
- **Clean Architecture & Separation of Concerns**:
  - `src/domain/`: Shared data structures, YAML/Markdown parsing, artifact indexing, frontmatter mutation, and state transitions.
  - `src/checkers/common.py`: Reusable checker infrastructure (file discovery, AST parsing with syntax `Finding` wrapping, Git status queries).
  - `src/checkers/*_checker.py`: Strictly domain-specific validation rules for each policy.
  - `src/orchestrator/`: Worktree isolation, MergeGate evaluation, parallel scheduling, lineage, documentation generation, and lifecycle commands.
  - `src/cli/`: Thin CLI argument parsing (`main.py`) and output contract formatting (`output.py`).
- **Hard Sizing Limits (`policy/limits.yaml`)**:
  - `max_file_lines: 500`
  - `max_function_lines: 40`
  - `max_function_args: 5`
  - `max_docstring_lines: 3` (`max_docstring_words: 35`)
  - `max_inline_comment_lines: 2` (`max_inline_comment_words: 25`)

## 3. Anti-Loop & Canonical Formatting Rules (`ruff format`)
- **Decompose, Never Line-Golf**: When a file approaches or exceeds `max_file_lines` (`500`), `max_function_lines` (`40`), or `max_mccabe_complexity` (`8`), **never** compact multi-line expressions, inline helpers, or golf formatting to save lines. Always extract cohesive logic into a shared module (`src/domain/`, `src/checkers/common.py`) or split the module and register new paths in `SPEC` `target_files` and `TASK` `write_files`.
- **Direct Canonical Formatting (`ruff format`)**: `mt check clean_code` (and `mt check all`) directly formats Python files in-place via `ruff format --quiet` before linting and before `mt check limits` measures line counts. Never manually wrap or unwrap lines; run `ruff format` or `./mt check all` directly.
- **Surgical Edits Only**: Never pass an entire file to `replace_file_content` to fix a localized lint or limit finding; restrict `StartLine`/`EndLine` to the specific function being modified.
- **One-Strike Circuit Breaker**: If an in-place edit fails `LIMIT_FILE_LINES`, `LIMIT_FUNC_LINES`, or `CODE_C901` once, stop editing in-place and extract a function or module immediately.


