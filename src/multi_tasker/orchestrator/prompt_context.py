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
    if agent_role == "review-agent":
        lines.append(
            "- **Semantic Review Rubric**: Verify complete upstream `traces_to` and "
            "`AcceptanceCriterion` coverage, realistic `target_files`/`write_files` "
            "bounds, and absence of scope creep or layer violations before emitting "
            "`verdict: pass`."
        )
    if agent_role == "worker-agent":
        lines.extend(_render_worker_limits_and_ast(repository_root))
    if agent_role in {"specification-agent", "planner-agent"}:
        hints = collect_refactoring_targets(repository_root)
        if hints:
            items = ", ".join(f"`{item.path}` ({item.line} lines)" for item in hints)
            lines.append(f"- **Refactoring Targets (Warning)**: {items}")
    return [*lines, *render_glossary_constraints(repository_root), ""]


def _render_code_file_block(
    repository_root: Path, heading_prefix: str, relative_path: str
) -> list[str]:
    """Render a Required File or Write File entry with inline content if present."""
    lines = [f"### {heading_prefix} `{relative_path}`", f"Path: `{relative_path}`"]
    file_path = repository_root / relative_path
    if file_path.is_file():
        lines.extend(["```python", file_path.read_text("utf-8").strip(), "```"])
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


def render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write/target files."""
    lines = ["## 4. Scoped Target & Upstream Context", ""]
    upstream_ids = [
        *target_document.frontmatter.get("traces_to", []),
        *target_document.frontmatter.get("decisions", []),
    ]
    context_docs = [
        target_document,
        *(
            by_identifier[str(item)]
            for item in upstream_ids
            if str(item) in by_identifier
        ),
    ]
    for document in context_docs:
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
    for path in target_document.frontmatter.get("required_files", []):
        if (repository_root / str(path)).is_file():
            lines.extend(
                _render_code_file_block(repository_root, "Required File", str(path))
            )
    for path in target_document.frontmatter.get("write_files", []):
        lines.extend(_render_code_file_block(repository_root, "Write File", str(path)))
    lines.extend(_render_spec_target_files(repository_root, target_document))
    return lines
