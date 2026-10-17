"""Deterministic MergeGate verification engine."""

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.checkers.common import get_git_changed_files
from src.checkers.permissions_checker import check_permissions
from src.checkers.runner import run_checks
from src.domain.models import Finding
from src.domain.parser import parse_artifact_file
from src.orchestrator.worktree import compute_policy_sha256

GATE_CHECK_SUITES = [
    "schemas",
    "clean_code",
    "limits",
    "glossary",
    "architecture",
    "traceability",
]


@dataclass(frozen=True)
class GateRequest:
    """Parameters for evaluating a Worktree at the MergeGate."""

    base_root: Path
    worktree_path: Path
    agent_role: str
    task_id: str | None = None
    verification_command: str | None = None
    changed_files: list[str] | None = None
    verification_timeout_seconds: float = 60.0


@dataclass(frozen=True)
class GateOutcome:
    """Result of a deterministic MergeGate evaluation."""

    passed: bool
    escalated: bool
    escalation_path: str | None
    findings: list[Finding]


def _load_base_artifact_states(
    base_root: Path, changed_files: list[str]
) -> dict[str, str]:
    """Read existing artifact status values from the trusted BaseBranch."""
    states: dict[str, str] = {}
    for relative_path in changed_files:
        absolute_path = base_root / relative_path
        if absolute_path.is_file() and relative_path.startswith("artifacts/"):
            document, _ = parse_artifact_file(absolute_path, relative_path)
            if document and "status" in document.frontmatter:
                states[relative_path] = str(document.frontmatter["status"])
    return states


def _run_verification_command(
    worktree_path: Path, command_string: str, timeout_seconds: float = 60.0
) -> list[Finding]:
    """Execute deterministic verification_command and emit a Finding on failure."""
    arguments = shlex.split(command_string)
    try:
        process = subprocess.run(
            arguments,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        message = f"Command '{command_string}' timed out after {timeout_seconds}s"
        return [Finding("verification_cmd", 1, "GATE_VERIFY_CMD_TIMEOUT", message)]
    if process.returncode == 0:
        return []
    lines = [
        line.strip()
        for line in (process.stdout + "\n" + process.stderr).splitlines()
        if line.strip()
    ]
    error_lines = [line for line in lines if line.startswith("E ")]
    if not lines:
        summary = f"Command '{command_string}' exited {process.returncode}"
    elif error_lines and error_lines[0] != lines[-1]:
        summary = f"{error_lines[0]} | {lines[-1]}"
    else:
        summary = lines[-1]
    return [Finding("verification_cmd", 1, "GATE_VERIFY_CMD_FAILED", summary)]


def _evaluate_escalation(worktree_path: Path, escalation_path: str) -> GateOutcome:
    """Validate an Escalation file against glossary and schemas policies."""
    escalation_findings = run_checks(
        worktree_path, ["glossary", "schemas"], target_paths=[escalation_path]
    )
    passed = len(escalation_findings) == 0
    return GateOutcome(
        False, passed, escalation_path if passed else None, escalation_findings
    )


def evaluate_merge_gate(request: GateRequest) -> GateOutcome:
    """Verify policy integrity, permissions, escalations, linters, and tests."""
    if compute_policy_sha256(request.base_root) != compute_policy_sha256(
        request.worktree_path
    ):
        message = "Worktree policy/** digest differs from trusted BaseBranch."
        finding = Finding("policy/permissions.yaml", 1, "GATE_POLICY_TAMPERED", message)
        return GateOutcome(False, False, None, [finding])
    changed = (
        request.changed_files
        if request.changed_files is not None
        else get_git_changed_files(request.worktree_path)
    )
    if not changed:
        message = "Agent exited without modifying any files or emitting an Escalation."
        return GateOutcome(
            False, False, None, [Finding("worktree", 1, "GATE_EMPTY_DIFF", message)]
        )
    states = _load_base_artifact_states(request.base_root, changed)
    permission_findings = check_permissions(
        request.worktree_path, request.agent_role, request.task_id, changed, states
    )
    if permission_findings:
        return GateOutcome(False, False, None, permission_findings)
    if len(changed) == 1 and changed[0].startswith("artifacts/escalations/"):
        return _evaluate_escalation(request.worktree_path, changed[0])
    findings = run_checks(
        request.worktree_path, GATE_CHECK_SUITES, target_paths=changed
    )
    if request.verification_command and not findings:
        findings.extend(
            _run_verification_command(
                request.worktree_path,
                request.verification_command,
                request.verification_timeout_seconds,
            )
        )
    return GateOutcome(len(findings) == 0, False, None, findings)
