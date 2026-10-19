"""Bidirectional Traceability lineage inspection (`mt trace`)."""

import ast
from pathlib import Path
import re

from multi_tasker.checkers.common import (
    extract_test_traces,
    get_git_commit_subjects,
    parse_python_ast,
)
from multi_tasker.domain.models import ArtifactDocument
from multi_tasker.domain.parser import load_artifacts_by_id

COMMIT_ID_REGEX = re.compile(r"\b(?:INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}\b")


def _extract_function_trace_links(
    node: ast.AST, relative_path: str
) -> list[tuple[str, str, str, str]]:
    """Extract (requirement_id, criterion_id, specification_id, location) from AST."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    location = f"{relative_path}:{node.name}"
    return [
        (req_id, criterion_id, spec_id, location)
        for req_id, criterion_id, spec_id in extract_test_traces(node)
    ]


def collect_test_trace_links(
    repository_root: Path,
) -> list[tuple[str, str, str, str]]:
    """Collect (requirement_id, criterion_id, specification_id, location) in tests/."""
    test_directory = repository_root / "tests"
    if not test_directory.exists():
        return []
    entries: list[tuple[str, str, str, str]] = []
    for python_path in sorted(test_directory.rglob("test_*.py")):
        relative_path = python_path.relative_to(repository_root).as_posix()
        source_code = python_path.read_text(encoding="utf-8")
        tree, syntax_errors = parse_python_ast(
            source_code, relative_path, "TRACE_TEST_SYNTAX"
        )
        if syntax_errors or tree is None:
            continue
        for node in ast.walk(tree):
            entries.extend(_extract_function_trace_links(node, relative_path))
    return entries


def _document_matches_target(document: ArtifactDocument, target: str) -> bool:
    """Return True if document matches target ID, path, references, or target_files."""
    frontmatter = document.frontmatter
    if str(frontmatter.get("id", "")) == target or document.path == target:
        return True
    for key in ("traces_to", "decisions", "depends_on", "applies_to", "write_files"):
        values = frontmatter.get(key, [])
        if isinstance(values, list) and target in {str(value) for value in values}:
            return True
    if target in {
        str(frontmatter.get("resolves", "")),
        str(frontmatter.get("resolved_by", "")),
    }:
        return True
    target_files = frontmatter.get("target_files")
    if isinstance(target_files, dict):
        all_target_files = [
            str(item)
            for item in target_files.get("tests", [])
            + target_files.get("implementation", [])
        ]
        if target in all_target_files:
            return True
    return False


def _expand_matched_ids(
    by_identifier: dict[str, ArtifactDocument], target: str
) -> set[str]:
    """Find all artifact IDs directly or transitively connected to target."""
    matched_ids = {
        artifact_id
        for artifact_id, document in by_identifier.items()
        if _document_matches_target(document, target)
    }
    for _ in range(2):
        for artifact_id, document in by_identifier.items():
            if any(
                _document_matches_target(document, matched_id)
                or _document_matches_target(by_identifier[matched_id], artifact_id)
                for matched_id in list(matched_ids)
            ):
                matched_ids.add(artifact_id)
    return matched_ids


def _collect_matching_commit_lines(
    repository_root: Path, target_ids: set[str]
) -> list[str]:
    """Return formatted COMMIT lines for git log entries referencing target_ids."""
    lines: list[str] = []
    for commit_hash, subject in get_git_commit_subjects(repository_root):
        referenced_ids = set(COMMIT_ID_REGEX.findall(subject))
        if referenced_ids & target_ids:
            lines.append(f"COMMIT {commit_hash} -> {subject}")
    return lines


def trace_lineage(repository_root: Path, target: str) -> list[str]:
    """Return formatted bidirectional lineage lines for an artifact ID or filepath."""
    by_identifier = load_artifacts_by_id(repository_root)
    matched_ids = _expand_matched_ids(by_identifier, target)
    lines: list[str] = []
    for artifact_id in sorted(matched_ids):
        frontmatter = by_identifier[artifact_id].frontmatter
        status = frontmatter.get("status", frontmatter.get("verdict", "ok"))
        lines.append(f"{artifact_id} [{status}] ({by_identifier[artifact_id].path})")
    for (
        requirement_id,
        criterion_id,
        specification_id,
        location,
    ) in collect_test_trace_links(repository_root):
        matches = {
            requirement_id,
            specification_id,
            f"{requirement_id}:{criterion_id}",
            location.split(":")[0],
        }
        if (
            target in matches
            or requirement_id in matched_ids
            or specification_id in matched_ids
        ):
            pair = f"{requirement_id}:{criterion_id}, {specification_id}"
            lines.append(f"TEST {location} -> {pair}")
    lines.extend(
        _collect_matching_commit_lines(repository_root, {target, *matched_ids})
    )
    return lines
