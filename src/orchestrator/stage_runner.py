"""Configurable per-agent Worktree stage runner (`mt run --agent <role>`)."""

import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any

from src.checkers.common import get_git_changed_files
from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import (
    load_artifacts_by_id,
    load_yaml_file,
    parse_artifact_file,
)
from src.orchestrator.documentation_generator import (
    write_repository_documentation,
)
from src.orchestrator.interaction_logger import (
    merge_worktree_task_logs,
    record_task_event,
)
from src.orchestrator.merge_gate import GateOutcome, GateRequest, evaluate_merge_gate
from src.orchestrator.prompt_builder import (
    build_agent_prompt,
    resolve_context_mode,
    resolve_task_execution,
)
from src.orchestrator.worktree import (
    commit_traceable_change,
    create_worktree,
    merge_worktree_files,
    remove_worktree,
)


def is_worktree_agent_enabled(repository_root: Path, agent_role: str) -> bool:
    """Return True if agent_role has worktree_execution enabled in permissions.yaml."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    if not permissions_path.exists():
        return True
    agents: dict[str, Any] = load_yaml_file(permissions_path).get("agents", {})
    role_config = agents.get(agent_role)
    if not isinstance(role_config, dict):
        return False
    return bool(role_config.get("worktree_execution", True))


def _snapshot_artifacts(root: Path) -> dict[str, str]:
    """Map relative artifact paths under root/artifacts to their text content."""
    artifacts_dir = root / "artifacts"
    if not artifacts_dir.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(artifacts_dir.rglob("*.md"))
        if path.is_file()
    }


def _detect_stage_changes(
    worktree_path: Path, before_snapshot: dict[str, str]
) -> list[str]:
    """Return modified or created relative paths inside worktree_path."""
    git_changed = get_git_changed_files(worktree_path)
    if git_changed:
        return git_changed
    after_snapshot = _snapshot_artifacts(worktree_path)
    return [
        path
        for path, content in sorted(after_snapshot.items())
        if before_snapshot.get(path) != content
    ]


def _prepare_stage_invocation(
    worktree_path: Path,
    agent_role: str,
    target_document: ArtifactDocument,
    execution_context: tuple[str, str, str],
) -> tuple[Path, str, dict[str, str]]:
    """Write .mt_prompt.md and build command and environment for stage execution."""
    target_id = str(target_document.frontmatter["id"])
    mode = resolve_context_mode(worktree_path, target_document)
    prompt_text, _ = build_agent_prompt(worktree_path, agent_role, target_id, mode)
    prompt_file = worktree_path / ".mt_prompt.md"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    command_template, environment_name, model_name = execution_context
    rendered = (
        command_template.replace("{model}", model_name)
        .replace("{task_id}", target_id)
        .replace("{agent_role}", agent_role)
        .replace("{prompt_file}", str(prompt_file))
        .replace("{context_mode}", mode)
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
        "MT_AGENT_ROLE": agent_role,
        "MT_TASK_ID": target_id,
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
        "MT_CONTEXT_MODE": mode,
    }
    return prompt_file, rendered, environment


def _run_stage_subprocess(
    worktree_path: Path,
    agent_role: str,
    target_document: ArtifactDocument,
    execution_context: tuple[str, str, str],
) -> list[str]:
    """Execute stage agent subprocess in worktree_path and return changed files."""
    target_id = str(target_document.frontmatter["id"])
    before = _snapshot_artifacts(worktree_path)
    prompt_file, rendered, environment = _prepare_stage_invocation(
        worktree_path, agent_role, target_document, execution_context
    )
    started = time.monotonic()
    try:
        process = subprocess.run(
            shlex.split(rendered),
            cwd=worktree_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=300.0,
        )
        details = {
            "command": rendered,
            "return_code": process.returncode,
            "timed_out": False,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }
        record_task_event(
            worktree_path, target_id, "agent_invocation", details, execution_context
        )
    finally:
        prompt_file.unlink(missing_ok=True)
    return _detect_stage_changes(worktree_path, before)


def _finalize_stage_outcome(
    request: GateRequest,
    target_id: str,
    outcome: GateOutcome,
) -> tuple[list[str], list[Finding]]:
    """Merge validated stage artifacts onto BaseBranch and commit traceable change."""
    if not outcome.passed:
        return [], outcome.findings
    changed_files = request.changed_files or []
    merge_worktree_files(request.base_root, request.worktree_path, changed_files)
    produced_ids: list[str] = []
    for relative_path in changed_files:
        document, _ = parse_artifact_file(
            request.base_root / relative_path, relative_path
        )
        if document and "id" in document.frontmatter:
            produced_ids.append(str(document.frontmatter["id"]))
    primary_id = produced_ids[0] if produced_ids else target_id
    traces_csv = ", ".join([target_id, *produced_ids])
    subject = (
        f"{primary_id}: Execute {request.agent_role} for {target_id} "
        f"[traces: {traces_csv}]"
    )
    commit_traceable_change(request.base_root, changed_files, subject)
    write_repository_documentation(request.base_root)
    return produced_ids or [target_id], []


def _validate_stage_request(
    repository_root: Path, agent_role: str, target_id: str
) -> tuple[ArtifactDocument | None, list[Finding]]:
    """Validate agent_role, worktree_execution flag, and target_id existence."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    agents: dict[str, Any] = permissions.get("agents", {})
    if agent_role not in agents:
        message = f"Unknown agent role '{agent_role}'."
        return None, [
            Finding("policy/permissions.yaml", 1, "CLI_UNKNOWN_AGENT_ROLE", message)
        ]
    if not is_worktree_agent_enabled(repository_root, agent_role):
        message = f"Agent '{agent_role}' has worktree_execution disabled."
        return None, [
            Finding(
                "policy/permissions.yaml", 1, "CLI_AGENT_WORKTREE_DISABLED", message
            )
        ]
    target_document = load_artifacts_by_id(repository_root).get(target_id)
    if target_document is None:
        message = f"Target artifact '{target_id}' not found."
        return None, [Finding(target_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    return target_document, []


def run_agent_stage(
    repository_root: Path,
    agent_role: str,
    target_id: str,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
) -> tuple[list[str], list[Finding]]:
    """Execute a configured agent_role for target_id in an isolated Worktree."""
    target_document, findings = _validate_stage_request(
        repository_root, agent_role, target_id
    )
    if findings or target_document is None:
        return [], findings
    worktree_path = create_worktree(repository_root, f"{agent_role}-{target_id}")
    try:
        context = resolve_task_execution(
            worktree_path, target_document, options, agent_role
        )
        changed = (
            _run_stage_subprocess(
                worktree_path,
                agent_role,
                target_document,
                (context[0], context[1], context[2]),
            )
            if context[0]
            else []
        )
        task_arg = target_id if agent_role == "worker-agent" else None
        request = GateRequest(
            repository_root, worktree_path, agent_role, task_arg, None, changed
        )
        outcome = evaluate_merge_gate(request)
        merge_worktree_task_logs(repository_root, worktree_path, target_id)
        return _finalize_stage_outcome(request, target_id, outcome)
    finally:
        remove_worktree(repository_root, worktree_path)
