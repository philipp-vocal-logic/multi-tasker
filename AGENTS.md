# AGENTS.md — Development Rules & Principles

## 1. Strict MVP Mindset (KISS & YAGNI)
- **Zero Backward Compatibility or Shims**: Greenfield MVP only. Never add fallback paths, deprecated aliases, wrapper functions, or re-exports. Move refactored symbols cleanly and update callers in lockstep.
- **Single Source of Truth**: `policy/*.yaml` and `artifacts/**` are the sole authoritative specification. Never maintain duplicate static specification or prompt files, and never hardcode configurable policy thresholds in documentation or instructions. Generate documentation (`./mt documentation` into gitignored `.report/specification.md`) and role prompts (`./mt prompt <role>`) deterministically from live repository state.
- **Separation of Specification and Interaction Logging**: Keep `.report/specification.md` (live repository `Specification` report) strictly separated from `.report/logs/` (`events.jsonl` and `tasks/<TARGET-ID>.jsonl` runtime CLI and `Worktree` execution logs).
- **Unabbreviated English Identifiers**: Never use abbreviations in filenames, CLI subcommands, classes, functions, parameters, or variables (e.g., `documentation_generator.py`, `interaction_logger.py`, `ArtifactDocument`, `relative_path`, `configuration`, `frontmatter`).
- **Read & Verify Before Answering or Editing**: Never guess or extrapolate CLI subcommands, flags, policy behavior, or existing test coverage from partial file reads. Before answering an architectural question or proposing changes, inspect `src/cli/main.py`, `.report/specification.md` (via `./mt documentation`), and the latest `REQ-*`/`SPEC-*`/`TASK-*` artifacts to verify actual repository state.

## 2. Mandatory Dogfooding & Artifact Lifecycle Workflow
Never edit `src/**`, `tests/**`, or completed (`done`) `TASK-NNN.md` artifacts ad-hoc. Every feature, bugfix, or refinement must progress through the canonical pipeline:
1. **Intent (`INT-NNN`)**: Run `./mt intent "<what to change and why>"` to create an `open` Intent in `artifacts/intents/INT-NNN.md`.
2. **Requirement (`REQ-NNN`)**: Author `artifacts/requirements/REQ-NNN.md` (`status: draft`, `traces_to: [INT-NNN]`) and run `./mt approve REQ-NNN` (transitions `REQ-NNN` to `approved` and `INT-NNN` to `processed`).
3. **Specification (`SPEC-NNN`)**: Author `artifacts/specifications/SPEC-NNN.md` (`status: draft`, `traces_to: [REQ-NNN]`), mapping all `REQ-NNN:AC-XX` criteria and declaring `target_files.tests` and `target_files.implementation`, and run `./mt approve SPEC-NNN` (transitions `SPEC-NNN` to `approved`).
4. **Tasks (`TASK-NNN`)**:
   - Create a `type: test_contract` Task (`write_files` under `tests/**` only) with `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")` tests.
   - Create `type: implementation` Tasks (`depends_on` the `test_contract` Task, `write_files` under `src/**` only, respecting `max_write_files` and `max_required_files` in `policy/schemas.yaml`).
5. **Isolated Execution, Review Gates & Diagnostics (`./mt run`)**: Execute planned Tasks (`./mt run`), individual agent stages (`./mt run --agent <role> --target <id>`), or the full declarative pipeline (`./mt run --pipeline`, governed by `policy/pipeline.yaml` `approval_gate` and `escalation_routes` with append-only `REV-*.md` verdicts) through the `Worktree` and `MergeGate` so each stage or Task produces a dedicated, scope-verified commit. Inspect `.report/logs/tasks/<TARGET-ID>.jsonl` and `.report/logs/events.jsonl` to diagnose agent subprocess, in-`Worktree` CLI, or `MergeGate` failures.

## 3. Architecture, Sizing Limits & Anti-Loop Rules
- **Zero-Noise Gate (`./mt check all`)**: All policies, artifacts, tests, and Git commits must pass `./mt check all` with a zero exit code and empty `stdout`.
- **Layer Boundaries (`policy/architecture.yaml`)**:
  ```mermaid
  flowchart RL
      tests["tests"] --> cli["cli"] --> orchestrator["orchestrator"] --> checkers["checkers"] --> domain["domain"]
  ```
- **Dynamic Policy Configuration (`policy/limits.yaml`, `policy/clean_code.yaml`, `policy/schemas.yaml`, `policy/permissions.yaml`, `policy/pipeline.yaml`)**: All file, function, argument, complexity, docstring, inline comment, artifact section, per-role model, stage approval gate, and escalation/review bounds are governed exclusively by `policy/*.yaml` (inspect active values via `./mt prompt <role>` or `./mt documentation`).
- **Decompose, Never Line-Golf (One-Strike Circuit Breaker)**: `mt check clean_code` formats Python files in-place via `ruff format --quiet` before `mt check limits` measures lines. If an edit fails `LIMIT_FILE_LINES`, `LIMIT_FUNC_LINES`, or `CODE_C901` once, stop editing in-place and extract a helper function or module immediately.
