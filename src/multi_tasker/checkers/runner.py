"""Unified runner for `mt check` subcommands."""

from pathlib import Path

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.checkers.clean_code_checker import check_clean_code
from multi_tasker.checkers.glossary_checker import check_glossary
from multi_tasker.checkers.limits_checker import check_limits
from multi_tasker.checkers.permissions_checker import check_permissions
from multi_tasker.checkers.schemas_checker import check_schemas
from multi_tasker.checkers.traceability_checker import check_traceability
from multi_tasker.domain.models import Finding

ALL_CHECKS: tuple[str, ...] = (
    "permissions",
    "schemas",
    "clean_code",
    "limits",
    "glossary",
    "architecture",
    "traceability",
)


def run_single_check(
    name: str,
    repository_root: Path,
    target_paths: list[str] | None = None,
    agent_role: str | None = None,
    task_id: str | None = None,
) -> list[Finding]:
    """Execute a single named checker and return its Findings."""
    if name == "permissions":
        return check_permissions(
            repository_root,
            agent_role=agent_role,
            task_id=task_id,
            changed_files=target_paths,
        )
    if name == "schemas":
        return check_schemas(repository_root, target_paths=target_paths)
    if name == "clean_code":
        return check_clean_code(repository_root, target_paths=target_paths)
    if name == "limits":
        return check_limits(repository_root, target_paths=target_paths)
    if name == "glossary":
        return check_glossary(repository_root, target_paths=target_paths)
    if name == "architecture":
        return check_architecture(repository_root, target_paths=target_paths)
    if name == "traceability":
        return check_traceability(repository_root, target_paths=target_paths)
    return [Finding("cli", 1, "CHECK_UNKNOWN", f"Unknown check '{name}'.")]


def run_checks(
    repository_root: Path,
    check_names: list[str],
    target_paths: list[str] | None = None,
    agent_role: str | None = None,
    task_id: str | None = None,
) -> list[Finding]:
    """Run one or more checks (or 'all') and return deduplicated sorted Findings."""
    expanded: list[str] = []
    for name in check_names:
        if name == "all":
            expanded.extend(ALL_CHECKS)
        else:
            expanded.append(name)
    findings: list[Finding] = []
    for name in dict.fromkeys(expanded):
        check_findings = run_single_check(
            name,
            repository_root,
            target_paths=target_paths,
            agent_role=agent_role,
            task_id=task_id,
        )
        findings.extend(check_findings)
        if name == "permissions" and check_findings:
            break
    return sorted(set(findings))
