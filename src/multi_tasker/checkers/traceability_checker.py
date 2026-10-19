"""Bidirectional artifact and code traceability checker (`mt check traceability`)."""

from pathlib import Path
from typing import Any

from multi_tasker.checkers import code_and_git_traceability
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import load_all_artifacts, load_yaml_file

LIST_REFERENCE_FIELDS = (
    "traces_to",
    "decisions",
    "depends_on",
    "affected_artifacts",
    "applies_to",
    "target_artifacts",
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


def _stage_active(target_paths: list[str] | None, prefixes: tuple[str, ...]) -> bool:
    """Return True if full-repo check or any path starts with prefixes."""
    return not target_paths or any(path.startswith(prefixes) for path in target_paths)


def _select_target_documents(
    by_identifier: dict[str, ArtifactDocument], target_paths: list[str] | None
) -> list[ArtifactDocument]:
    """Return all documents or only those matching target_paths when specified."""
    if not target_paths:
        return list(by_identifier.values())
    target_set = set(target_paths)
    return [doc for doc in by_identifier.values() if doc.path in target_set]


def _check_task_and_code_stages(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    target_paths: list[str] | None,
    rules: dict[str, Any],
) -> list[Finding]:
    """Run TestContract, Task cycle, target_files, and Git history checks."""
    findings: list[Finding] = []
    if _stage_active(target_paths, ("tests/", "src/")):
        findings.extend(
            code_and_git_traceability.check_test_contract_coverage(
                repository_root, by_identifier, rules
            )
        )
    task_prefixes = ("artifacts/tasks/", "tests/", "src/")
    if rules.get("forbid_dependency_cycles_in_tasks", True) and _stage_active(
        target_paths, task_prefixes
    ):
        findings.extend(_check_task_cycles_and_dependencies(by_identifier))
    if _stage_active(target_paths, task_prefixes):
        findings.extend(
            code_and_git_traceability.check_specification_target_files(
                repository_root, by_identifier, target_paths, rules
            )
        )
    if not target_paths:
        findings.extend(
            code_and_git_traceability.check_git_commit_history(
                repository_root, by_identifier, rules
            )
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
    for document in _select_target_documents(by_identifier, target_paths):
        findings.extend(_check_document_references(document, by_identifier, rules))
    spec_prefixes = ("artifacts/specifications/", "artifacts/tasks/", "tests/", "src/")
    if rules.get("require_100_percent_req_ac_covered_by_spec", True) and _stage_active(
        target_paths, spec_prefixes
    ):
        findings.extend(_check_requirement_to_specification_coverage(by_identifier))
    findings.extend(
        _check_task_and_code_stages(repository_root, by_identifier, target_paths, rules)
    )
    return sorted(set(findings))
