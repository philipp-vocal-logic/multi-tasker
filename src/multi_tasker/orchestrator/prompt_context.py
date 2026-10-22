"""Vocabulary, line-wrapping, and target context helpers for role prompt synthesis."""

from pathlib import Path
import textwrap
from typing import Any

from multi_tasker.checkers.limits_checker import collect_refactoring_targets
from multi_tasker.domain.models import ArtifactDocument
from multi_tasker.domain.parser import load_yaml_file

MAX_PROMPT_LINE_LENGTH: int = 88


def wrap_prompt_lines(lines: list[str]) -> list[str]:
    """Wrap synthesized Markdown lines outside code fences to MAX_PROMPT_LINE_LENGTH."""
    wrapped: list[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            wrapped.append(line)
        elif in_fence or len(line) <= MAX_PROMPT_LINE_LENGTH:
            wrapped.append(line)
        else:
            pad = (
                "     "
                if line.startswith("  ")
                else ("  " if line.startswith("- ") else "")
            )
            wrapped.extend(
                textwrap.wrap(
                    line,
                    width=MAX_PROMPT_LINE_LENGTH,
                    subsequent_indent=pad,
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
    return wrapped


def render_glossary_constraints(repository_root: Path) -> list[str]:
    """Render canonical Glossary terms with code_identifiers and Forbidden Synonyms."""
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if not glossary_path.exists():
        return []
    terms: list[dict[str, Any]] = load_yaml_file(glossary_path).get("terms", [])
    glossary_entries = [
        f"`{item.get('canonical')}` "
        f"({', '.join(str(cid) for cid in item.get('code_identifiers', [])[:4])})"
        for item in terms
        if item.get("canonical")
    ]
    forbidden_pairs = [
        f"`{item.get('canonical')}` != "
        f"{', '.join(item.get('forbidden_synonyms', [])[:3])}"
        for item in terms
        if item.get("forbidden_synonyms")
    ]
    return [
        f"- **Glossary Terms**: {'; '.join(glossary_entries)}",
        f"- **Forbidden Synonyms**: {'; '.join(forbidden_pairs)}",
    ]


def _format_layer_entry(item: dict[str, Any]) -> str:
    """Format a single layer name with path globs and allowed_internal_imports."""
    paths = ", ".join(str(path) for path in item.get("paths", []))
    imports = ", ".join(str(imp) for imp in item.get("allowed_internal_imports", []))
    return f"`{item.get('name')}` ({paths}; imports: {imports})"


def render_architecture_layers(repository_root: Path) -> list[str]:
    """Render defined layer names, path globs, and allowed_internal_imports."""
    arch_path = repository_root / "policy" / "architecture.yaml"
    if not arch_path.exists():
        return []
    layers = load_yaml_file(arch_path).get("layers", [])
    entries = [
        _format_layer_entry(item)
        for item in layers
        if isinstance(item, dict) and item.get("name")
    ]
    return [f"- **Architecture Layers**: {', '.join(entries)}"] if entries else []


def _render_worker_limits_and_ast(repository_root: Path) -> list[str]:
    """Render Source Limits (including max_line_length) and Clean Code AST Rules."""
    lines: list[str] = []
    limits_path = repository_root / "policy" / "limits.yaml"
    if limits_path.exists():
        source_limits = load_yaml_file(limits_path).get("source_code", {})
        limit_items = [
            f"`max_line_length={MAX_PROMPT_LINE_LENGTH}`",
            *(f"`{key}={val}`" for key, val in source_limits.items()),
        ]
        lines.append(f"- **Source Limits**: {', '.join(limit_items)}")
    clean_path = repository_root / "policy" / "clean_code.yaml"
    if clean_path.exists():
        ast_rules = load_yaml_file(clean_path).get("ast_rules", {})
        pairs = ", ".join(f"`{key}={val}`" for key, val in ast_rules.items())
        lines.append(f"- **Clean Code AST Rules**: {pairs}")
    return lines


def render_decomposition_contract(agent_role: str, next_id: str | None) -> list[str]:
    """Render Requirement or Planner decomposition contract for agent_role."""
    if agent_role == "requirement-agent":
        return [
            "- **Requirement Decomposition Contract**: Author one atomic `REQ` file "
            f"(starting at `id: {next_id or 'REQ-NNN'}`) per distinct capability in "
            "the `Intent` (declaring `supersedes: [REQ-NNN]` to deprecate any "
            "replaced `REQ` from the catalog below), and evaluate that single "
            "capability across good, edge, and failure `AcceptanceCriteria` "
            "(`AC-01`, `AC-02`, `AC-03`, ...)."
        ]
    if agent_role == "planner-agent":
        return [
            f"- **Planner Decomposition Contract**: Author single-concern "
            f"`type: test_contract` Task(s) (`id: {next_id}`, `traces_to: "
            "[REQ-NNN, SPEC-NNN]`, `write_files` covering `SPEC` "
            "`target_files.tests` without `_and_` test filenames, "
            "`verification_cmd: python3 -m py_compile <test_file>`, "
            'decorating tests with `@traces("REQ-NNN", "AC-XX", '
            '"SPEC-NNN")`) and `type: implementation` Task(s) (`traces_to: '
            f"[REQ-NNN, SPEC-NNN]`, `depends_on: [{next_id}]`, "
            "`required_files: [<test_file>]`, `write_files` covering "
            "`SPEC` `target_files.implementation`, "
            "`verification_cmd: pytest -q <test_file>`)."
        ]
    return []


def render_code_and_glossary_section(
    repository_root: Path, agent_role: str
) -> list[str]:
    """Render architecture layers, sizing limits, AST rules, and glossary terms."""
    lines = [
        "## 3. Vocabulary & Engineering Constraints",
        *render_architecture_layers(repository_root),
    ]
    if agent_role != "requirement-agent":
        lines.append(
            "- **TestContract Decorator**: "
            "`from multi_tasker.domain.models import traces` "
            'with 3 string arguments `@traces("REQ-NNN", "AC-XX", "SPEC-NNN")`'
        )
        lines.extend(_render_worker_limits_and_ast(repository_root))
    if agent_role == "review-agent":
        lines.append(
            "- **Semantic Review Rubric**: Verify a single cohesive capability per "
            "`REQ` evaluated across good, edge, and failure `AcceptanceCriteria`, "
            "complete upstream `traces_to` and `AcceptanceCriterion` coverage, "
            "realistic `target_files`/`write_files` bounds, and absence of scope "
            "creep or layer violations before emitting `verdict: pass`."
        )
    if agent_role in {"specification-agent", "planner-agent"}:
        hints = collect_refactoring_targets(repository_root)
        if hints:
            items = ", ".join(f"`{item.path}` ({item.line} lines)" for item in hints)
            lines.append(f"- **Refactoring Targets (Warning)**: {items}")
    return [*lines, *render_glossary_constraints(repository_root), ""]


def _render_code_file_block(
    repository_root: Path, heading_prefix: str, relative_path: str
) -> list[str]:
    """Render a Required File or Write File entry with inline content or new status."""
    lines = [f"### {heading_prefix} `{relative_path}`", f"Path: `{relative_path}`"]
    file_path = repository_root / relative_path
    if file_path.is_file():
        fence = "markdown" if relative_path.endswith(".md") else "python"
        lines.extend([f"```{fence}", file_path.read_text("utf-8").strip(), "```"])
    else:
        lines.append(
            "Status: New file (does not exist on disk yet; create at this path)."
        )
    return [*lines, ""]


def _render_spec_target_files(
    repository_root: Path, target_document: ArtifactDocument
) -> list[str]:
    """Render existing target_files (tests and implementation) from a SPEC artifact."""
    target_files = target_document.frontmatter.get("target_files", {})
    if not isinstance(target_files, dict):
        return []
    paths = [
        *target_files.get("tests", []),
        *target_files.get("implementation", []),
    ]
    lines: list[str] = []
    for path in paths:
        if (repository_root / str(path)).is_file():
            lines.extend(
                _render_code_file_block(repository_root, "Target File", str(path))
            )
    return lines


def _render_existing_requirements_catalog(
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render an index of existing Requirements when targeting an Intent."""
    if target_document.artifact_type != "INT":
        return []
    entries = [
        f"- `{req_id}`: {doc.frontmatter.get('title', req_id)} "
        f"(`status: {doc.frontmatter.get('status', 'draft')}`, "
        f"`version: {doc.frontmatter.get('version', 1)}`)"
        for req_id, doc in sorted(by_identifier.items())
        if doc.artifact_type == "REQ" and doc.frontmatter.get("status") != "deprecated"
    ]
    if not entries:
        return []
    return ["### Existing Requirements Catalog", *entries, ""]


def _collect_superseded_context(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> tuple[list[ArtifactDocument], list[str]]:
    """Return superseded REQ/SPEC documents and their existing target_files blocks."""
    superseded_reqs = [
        str(item)
        for item in target_document.frontmatter.get("supersedes", [])
        if str(item) in by_identifier
    ]
    req_set = set(superseded_reqs)
    superseded_specs = [
        doc
        for _, doc in sorted(by_identifier.items())
        if doc.artifact_type == "SPEC"
        and req_set & {str(ref) for ref in doc.frontmatter.get("traces_to", [])}
    ]
    docs = [*(by_identifier[rid] for rid in superseded_reqs), *superseded_specs]
    file_lines = [
        line
        for spec_doc in superseded_specs
        for line in _render_spec_target_files(repository_root, spec_doc)
    ]
    return docs, file_lines


def _collect_review_feedback_docs(
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[ArtifactDocument]:
    """Return rejected downstream draft artifacts and failed REV documents."""
    target_id = str(target_document.frontmatter.get("id", ""))
    downstream_drafts = [
        doc
        for _, doc in sorted(by_identifier.items())
        if str(doc.frontmatter.get("status", "")) in {"draft", "blocked"}
        and target_id in {str(ref) for ref in doc.frontmatter.get("traces_to", [])}
    ]
    relevant_ids = {
        target_id,
        *(str(doc.frontmatter.get("id", "")) for doc in downstream_drafts),
    }
    failed_reviews = [
        doc
        for _, doc in sorted(by_identifier.items())
        if doc.artifact_type == "REV"
        and doc.frontmatter.get("verdict") == "fail"
        and relevant_ids
        & {str(ref) for ref in doc.frontmatter.get("target_artifacts", [])}
    ]
    return [*downstream_drafts, *failed_reviews]


def _render_artifact_blocks(
    repository_root: Path, candidates: list[ArtifactDocument]
) -> tuple[list[str], set[str]]:
    """Render deduplicated Markdown artifact blocks and return rendered paths."""
    lines: list[str] = []
    rendered_paths: set[str] = set()
    for document in candidates:
        if document.path in rendered_paths:
            continue
        rendered_paths.add(document.path)
        artifact_id = str(document.frontmatter.get("id", document.path))
        raw = (repository_root / document.path).read_text("utf-8").strip()
        lines.extend(
            [
                f"### Artifact `{artifact_id}` (`{document.path}`)",
                f"Path: `{document.path}`",
                "```markdown",
                raw,
                "```",
                "",
            ]
        )
    return lines, rendered_paths


def render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write/target files."""
    superseded_docs, superseded_files = _collect_superseded_context(
        repository_root, target_document, by_identifier
    )
    upstream_ids = [
        *target_document.frontmatter.get("traces_to", []),
        *target_document.frontmatter.get("decisions", []),
        *target_document.frontmatter.get("affected_artifacts", []),
        *target_document.frontmatter.get("target_artifacts", []),
    ]
    candidates = [
        target_document,
        *(
            by_identifier[str(item)]
            for item in upstream_ids
            if str(item) in by_identifier
        ),
        *superseded_docs,
        *_collect_review_feedback_docs(target_document, by_identifier),
    ]
    artifact_lines, rendered_paths = _render_artifact_blocks(
        repository_root, candidates
    )
    lines = [
        "## 4. Scoped Target & Upstream Context",
        "",
        *artifact_lines,
        *_render_existing_requirements_catalog(target_document, by_identifier),
    ]
    for path in target_document.frontmatter.get("required_files", []):
        rel_path = str(path)
        if rel_path not in rendered_paths and (repository_root / rel_path).is_file():
            lines.extend(
                _render_code_file_block(repository_root, "Required File", rel_path)
            )
    for path in target_document.frontmatter.get("write_files", []):
        lines.extend(_render_code_file_block(repository_root, "Write File", str(path)))
    lines.extend(_render_spec_target_files(repository_root, target_document))
    lines.extend(superseded_files)
    return lines
