"""Bidirectional artifact and code traceability checker (`mt check traceability`)."""

import ast
from pathlib import Path
import re
from typing import Any

from src.checkers.common import (
    collect_repository_files,
    extract_test_traces,
    get_git_commit_subjects,
    parse_python_ast,
)
from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import load_all_artifacts, load_yaml_file

DEFAULT_COMMIT_PATTERN = (
    r"^(INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}: .+ "
    r"\[traces: [A-Z]+-[0-9]{3,}(?:, [A-Z]+-[0-9]{3,})*\]$"
)
ARTIFACT_ID_REGEX = re.compile(r"\b(?:INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}\b")

LIST_REFERENCE_FIELDS = (
    "traces_to",
    "decisions",
    "depends_on",
    "affected_artifacts",
    "applies_to",
)


def _collect_document_reference_ids(frontmatter: dict[str, Any]) -> list[str]:
    """Extract all referenced artifact IDs from frontmatter fields."""
    references = [
        str(item)
        for field in LIST_REFERENCE_FIELDS
        if isinstance(frontmatter.get(field), list)
        for item in frontmatter[field]
    ]
    for scalar in ("resolves", "resolved_by"):
        value = frontmatter.get(scalar)
        if isinstance(value, str) and value:
            references.append(value)
    return references


def _check_document_references(
    document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
    rules: dict[str, Any],
) -> list[Finding]:
    """Verify referenced IDs exist and upstream REQ/SPEC/DEC are approved."""
    findings: list[Finding] = []
    frontmatter = document.frontmatter
    if rules.get("require_all_referenced_ids_exist", True):
        for reference_id in _collect_document_reference_ids(frontmatter):
            if reference_id not in by_identifier:
                message = f"Referenced ID '{reference_id}' does not exist."
                findings.append(Finding(document.path, 1, "TRACE_MISSING_REF", message))
    check_spec = document.artifact_type == "SPEC" and rules.get(
        "require_upstream_approved_for_spec", True
    )
    check_task = document.artifact_type == "TASK" and rules.get(
        "require_upstream_approved_for_task", True
    )
    if check_spec or check_task:
        upstream_ids = frontmatter.get("traces_to", []) + frontmatter.get(
            "decisions", []
        )
        for upstream_id in (str(item) for item in upstream_ids):
            upstream = by_identifier.get(upstream_id)
            if upstream and upstream.frontmatter.get("status") != "approved":
                message = f"Upstream '{upstream_id}' is not 'approved'."
                findings.append(
                    Finding(document.path, 1, "TRACE_UPSTREAM_NOT_APPROVED", message)
                )
    return findings


def _check_requirement_to_specification_coverage(
    by_identifier: dict[str, ArtifactDocument],
) -> list[Finding]:
    """Verify every approved REQ AcceptanceCriterion is covered by a SPEC."""
    covered = {
        str(item)
        for document in by_identifier.values()
        if document.artifact_type == "SPEC"
        and document.frontmatter.get("status") != "deprecated"
        for item in document.frontmatter.get("covers_criteria", [])
    }
    findings: list[Finding] = []
    for document in by_identifier.values():
        if (
            document.artifact_type == "REQ"
            and document.frontmatter.get("status") == "approved"
        ):
            for criterion in document.frontmatter.get("acceptance_criteria", []):
                key = f"{document.frontmatter.get('id', '')}:{criterion.get('id', '')}"
                if isinstance(criterion, dict) and key not in covered:
                    message = f"AcceptanceCriterion '{key}' is not covered."
                    findings.append(
                        Finding(document.path, 1, "TRACE_UNCOVERED_REQ_AC", message)
                    )
    return findings


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


def _check_implementation_task_test_dependency(
    document: ArtifactDocument, tasks: dict[str, ArtifactDocument]
) -> list[Finding]:
    """Verify an implementation task depends on a test_contract task."""
    if document.frontmatter.get("type") != "implementation":
        return []
    dependencies = [str(item) for item in document.frontmatter.get("depends_on", [])]
    required = [str(item) for item in document.frontmatter.get("required_files", [])]
    has_test = any(
        tasks.get(dependency) is not None
        and tasks[dependency].frontmatter.get("type") == "test_contract"
        for dependency in dependencies
    )
    if not has_test or not any(item.startswith("tests/") for item in required):
        message = "Implementation Task must depend on a test_contract Task."
        return [Finding(document.path, 1, "TRACE_IMPL_MISSING_TEST_DEP", message)]
    return []


def _check_task_cycles_and_dependencies(
    by_identifier: dict[str, ArtifactDocument],
) -> list[Finding]:
    """Detect dependency cycles and missing test dependencies across Tasks."""
    tasks = {
        key: document
        for key, document in by_identifier.items()
        if document.artifact_type == "TASK"
    }
    visited, active, findings = set(), set(), []

    def depth_first_search(task_id: str) -> None:
        visited.add(task_id)
        active.add(task_id)
        document = tasks[task_id]
        for dependency in (
            str(item) for item in document.frontmatter.get("depends_on", [])
        ):
            if dependency not in visited and dependency in tasks:
                depth_first_search(dependency)
            elif dependency in active:
                message = f"Cycle detected in depends_on involving '{task_id}'."
                findings.append(Finding(document.path, 1, "TRACE_TASK_CYCLE", message))
        active.remove(task_id)

    for task_id, document in sorted(tasks.items()):
        if task_id not in visited:
            depth_first_search(task_id)
        findings.extend(_check_implementation_task_test_dependency(document, tasks))
    return findings


def _extract_specification_files(document: ArtifactDocument) -> list[str]:
    """Return all target_files paths declared on a SPEC document."""
    target_files = document.frontmatter.get("target_files")
    if document.artifact_type != "SPEC" or not isinstance(target_files, dict):
        return []
    combined = (*target_files.get("tests", []), *target_files.get("implementation", []))
    return [str(item) for item in combined]


def _check_specification_target_files(
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


def _stage_active(target_paths: list[str] | None, prefixes: tuple[str, ...]) -> bool:
    """Return True if full-repo check or any path starts with prefixes."""
    return not target_paths or any(path.startswith(prefixes) for path in target_paths)


def _check_git_commit_history(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    rules: dict[str, Any],
) -> list[Finding]:
    """Validate git log subjects against commit_message_pattern and artifact IDs."""
    pattern_text = str(rules.get("commit_message_pattern", DEFAULT_COMMIT_PATTERN))
    if not rules.get("verify_git_commit_traceability", True):
        return []
    compiled_pattern = re.compile(pattern_text)
    findings: list[Finding] = []
    for commit_hash, subject in get_git_commit_subjects(repository_root):
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
    return findings


def _check_test_contract_coverage(
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


def check_traceability(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/traceability.yaml and stage-aware bidirectional traceability."""
    traceability_path = repository_root / "policy" / "traceability.yaml"
    if not traceability_path.exists():
        message = "Missing policy/traceability.yaml."
        return [Finding("policy/traceability.yaml", 1, "TRACE_POLICY_MISSING", message)]
    rules = load_yaml_file(traceability_path).get("traceability_rules", {})
    by_identifier, findings = load_all_artifacts(repository_root)
    for document in by_identifier.values():
        findings.extend(_check_document_references(document, by_identifier, rules))
    spec_prefixes = ("artifacts/specifications/", "artifacts/tasks/", "tests/", "src/")
    if rules.get("require_100_percent_req_ac_covered_by_spec", True) and _stage_active(
        target_paths, spec_prefixes
    ):
        findings.extend(_check_requirement_to_specification_coverage(by_identifier))
    if _stage_active(target_paths, ("tests/", "src/")):
        findings.extend(
            _check_test_contract_coverage(repository_root, by_identifier, rules)
        )
    if rules.get("forbid_dependency_cycles_in_tasks", True):
        findings.extend(_check_task_cycles_and_dependencies(by_identifier))
    if _stage_active(target_paths, ("artifacts/tasks/", "tests/", "src/")):
        findings.extend(
            _check_specification_target_files(
                repository_root, by_identifier, target_paths, rules
            )
        )
    findings.extend(_check_git_commit_history(repository_root, by_identifier, rules))
    return sorted(set(findings))
