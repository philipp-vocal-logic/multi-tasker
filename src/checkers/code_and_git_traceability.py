"""Code, TestContract, target_files, and Git commit Traceability validator."""

import ast
from pathlib import Path
import re
from typing import Any

from src.checkers.common import (
    collect_repository_files,
    extract_test_traces,
    get_git_commit_files,
    get_git_commit_subjects,
    parse_python_ast,
)
from src.domain.models import ArtifactDocument, Finding

DEFAULT_COMMIT_PATTERN = (
    r"^(INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}: .+ "
    r"\[traces: [A-Z]+-[0-9]{3,}(?:, [A-Z]+-[0-9]{3,})*\]$"
)
ARTIFACT_ID_REGEX = re.compile(r"\b(?:INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}\b")


def _check_test_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative: str,
    decorator_name: str,
    argument_count: int,
    by_identifier: dict[str, ArtifactDocument],
) -> tuple[set[tuple[str, str]], list[Finding]]:
    """Validate @traces decorator tags on a single test function."""
    tags = extract_test_traces(node, decorator_name, argument_count)
    if not tags:
        message = f"Test '{node.name}' missing @{decorator_name}."
        return set(), [Finding(relative, node.lineno, "TRACE_UNTAGGED_TEST", message)]
    pairs = {
        (f"{req_id}:{criterion_id}", spec_id) for req_id, criterion_id, spec_id in tags
    }
    message = f"Test '{node.name}' references unknown ID."
    findings = [
        Finding(relative, node.lineno, "TRACE_INVALID_TAG", message)
        for req_id, _, spec_id in tags
        if req_id not in by_identifier or spec_id not in by_identifier
    ]
    return pairs, findings


def _scan_test_contracts(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    rules: dict[str, Any],
) -> tuple[set[tuple[str, str]], list[Finding]]:
    """Scan tests/** for @traces decorators and validate referenced IDs."""
    test_directory = repository_root / "tests"
    if not test_directory.exists():
        return set(), []
    decorator_name = str(rules.get("test_decorator_name", "traces"))
    signature = rules.get("test_decorator_signature", ["req_id", "ac_id", "spec_id"])
    argument_count = len(signature) if isinstance(signature, list) else 3
    covered_pairs, findings = set(), []
    function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
    for python_path in sorted(test_directory.rglob("test_*.py")):
        relative = python_path.relative_to(repository_root).as_posix()
        tree, errors = parse_python_ast(
            python_path.read_text(encoding="utf-8"), relative, "TRACE_TEST_SYNTAX"
        )
        findings.extend(errors)
        for node in ast.walk(tree) if tree else ():
            if isinstance(node, function_types) and node.name.startswith("test_"):
                pairs, node_findings = _check_test_function(
                    node, relative, decorator_name, argument_count, by_identifier
                )
                covered_pairs.update(pairs)
                findings.extend(node_findings)
    return covered_pairs, findings


def check_test_contract_coverage(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    rules: dict[str, Any],
) -> list[Finding]:
    """Verify @traces decorators and 100 percent SPEC AcceptanceCriterion coverage."""
    covered, findings = _scan_test_contracts(repository_root, by_identifier, rules)
    if rules.get("require_100_percent_spec_ac_covered_by_test_decorator", True):
        findings.extend(
            Finding(document.path, 1, "TRACE_MISSING_TEST_CONTRACT", "Untested AC.")
            for document in by_identifier.values()
            if document.artifact_type == "SPEC"
            and document.frontmatter.get("status") == "approved"
            for item in document.frontmatter.get("covers_criteria", [])
            if (str(item), str(document.frontmatter.get("id", ""))) not in covered
        )
    return findings


def _extract_specification_files(document: ArtifactDocument) -> list[str]:
    """Return all target_files paths declared on a SPEC document."""
    target_files = document.frontmatter.get("target_files")
    if document.artifact_type != "SPEC" or not isinstance(target_files, dict):
        return []
    combined = (*target_files.get("tests", []), *target_files.get("implementation", []))
    return [str(item) for item in combined]


def check_specification_target_files(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    target_paths: list[str] | None,
    rules: dict[str, Any],
) -> list[Finding]:
    """Verify target_files declarations on disk and in TASK write_files."""
    declared = {
        path
        for document in by_identifier.values()
        for path in _extract_specification_files(document)
    }
    findings: list[Finding] = []
    if declared and rules.get("require_files_declared_in_spec_target_files", True):
        for file_path in collect_repository_files(
            repository_root, target_paths, ("src", "tests"), {".py"}
        ):
            relative = file_path.relative_to(repository_root).as_posix()
            if Path(relative).name != "__init__.py" and relative not in declared:
                message = f"File '{relative}' is not declared in any SPEC target_files."
                findings.append(
                    Finding(relative, 1, "ARCH_UNDECLARED_TARGET_FILE", message)
                )
    task_writes = {
        str(path)
        for document in by_identifier.values()
        if document.artifact_type == "TASK"
        for path in document.frontmatter.get("write_files", [])
    }
    if task_writes and rules.get("require_spec_target_files_covered_by_tasks", True):
        findings.extend(
            Finding(document.path, 1, "TRACE_UNPLANNED_TARGET_FILE", path)
            for document in by_identifier.values()
            if document.frontmatter.get("status") == "approved"
            for path in _extract_specification_files(document)
            if path not in task_writes
        )
    return findings


def _check_task_commit_scope(
    repository_root: Path,
    commit_hash: str,
    subject: str,
    by_identifier: dict[str, ArtifactDocument],
) -> list[Finding]:
    """Verify a TASK-NNN commit only modifies files within its write_files scope."""
    prefix = subject.split(":", maxsplit=1)[0].strip()
    task_document = by_identifier.get(prefix)
    if not prefix.startswith("TASK-") or task_document is None:
        return []
    allowed_writes = {
        str(item) for item in task_document.frontmatter.get("write_files", [])
    }
    upstream_prefixes = (
        "artifacts/intents/",
        "artifacts/requirements/",
        "artifacts/specifications/",
    )
    findings: list[Finding] = []
    for changed in get_git_commit_files(repository_root, commit_hash):
        unscoped_code = (
            changed.startswith(("src/", "tests/"))
            and Path(changed).name != "__init__.py"
            and changed not in allowed_writes
        )
        if unscoped_code or changed.startswith(upstream_prefixes):
            message = f"Commit '{commit_hash}' modifies unscoped file '{changed}'."
            findings.append(
                Finding("git-log", 1, "TRACE_COMMIT_UNSCOPED_FILE", message)
            )
    return findings


def _check_intent_to_requirement_coverage(
    by_identifier: dict[str, ArtifactDocument],
) -> list[Finding]:
    """Verify every processed Intent is referenced by at least one Requirement."""
    covered_intents = {
        str(item)
        for document in by_identifier.values()
        if document.artifact_type == "REQ"
        for item in document.frontmatter.get("traces_to", [])
    }
    return [
        Finding(
            document.path,
            1,
            "TRACE_UNPROCESSED_INTENT",
            f"Processed Intent '{document.frontmatter.get('id')}' has no Requirement.",
        )
        for document in by_identifier.values()
        if document.artifact_type == "INT"
        and document.frontmatter.get("status") == "processed"
        and str(document.frontmatter.get("id", "")) not in covered_intents
    ]


def check_git_commit_history(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    rules: dict[str, Any],
) -> list[Finding]:
    """Validate git log subjects, Task commit write scopes, and Intent coverage."""
    pattern_text = str(rules.get("commit_message_pattern", DEFAULT_COMMIT_PATTERN))
    commits = get_git_commit_subjects(repository_root)
    if not rules.get("verify_git_commit_traceability", True) or not commits:
        return []
    compiled_pattern = re.compile(pattern_text)
    findings = _check_intent_to_requirement_coverage(by_identifier)
    for commit_hash, subject in commits:
        if not compiled_pattern.match(subject):
            message = f"Commit '{commit_hash}' subject '{subject}' is not traceable."
            findings.append(Finding("git-log", 1, "TRACE_COMMIT_FORMAT", message))
            continue
        for artifact_id in ARTIFACT_ID_REGEX.findall(subject):
            if artifact_id not in by_identifier:
                message = (
                    f"Commit '{commit_hash}' references unknown ID '{artifact_id}'."
                )
                findings.append(
                    Finding("git-log", 1, "TRACE_COMMIT_UNKNOWN_ID", message)
                )
        findings.extend(
            _check_task_commit_scope(
                repository_root, commit_hash, subject, by_identifier
            )
        )
    return findings
