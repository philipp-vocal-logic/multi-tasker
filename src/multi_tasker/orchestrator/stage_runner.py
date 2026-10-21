"""Configurable per-agent Worktree stage and declarative pipeline runner."""

import os
from pathlib import Path
import shlex
import subprocess
import time
from typing import Any

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import (
    load_artifacts_by_id,
    load_pipeline_policy,
    load_yaml_file,
    normalize_new_stage_artifacts,
    parse_artifact_file,
    update_artifact_frontmatter,
)
from multi_tasker.orchestrator.documentation_generator import (
    write_repository_documentation,
)
from multi_tasker.orchestrator.interaction_logger import (
    merge_worktree_task_logs,
    record_task_event,
)
from multi_tasker.orchestrator.lifecycle import (
    approve_stage_artifact,
    evaluate_review_verdict,
)
from multi_tasker.orchestrator.merge_gate import (
    GateOutcome,
    GateRequest,
    evaluate_merge_gate,
)
from multi_tasker.orchestrator.prompt_builder import (
    build_agent_prompt,
    resolve_task_execution,
)
from multi_tasker.orchestrator.router import (
    CATEGORY_ROUTES,
    find_actionable_stage_target,
)
from multi_tasker.orchestrator.task_runner import run_scheduled_tasks
from multi_tasker.orchestrator.worktree import (
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
    return (
        bool(role_config.get("worktree_execution", True))
        if isinstance(role_config, dict)
        else False
    )


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
    worktree_path: Path, before_snapshot: dict[str, str], target_id: str = ""
) -> list[str]:
    """Return modified or created relative paths inside worktree_path."""
    git_changed = get_git_changed_files(worktree_path)
    changed = git_changed or [
        path
        for path, content in sorted(_snapshot_artifacts(worktree_path).items())
        if before_snapshot.get(path) != content
    ]
    editable = ("status: draft", "status: needs_update", "status: blocked")
    locked_ids = {
        Path(path).stem
        for path, text in before_snapshot.items()
        if Path(path).stem != target_id and not any(tag in text for tag in editable)
    }
    return normalize_new_stage_artifacts(worktree_path, locked_ids, changed)


def _prepare_stage_invocation(
    worktree_path: Path,
    agent_role: str,
    target_document: ArtifactDocument,
    execution_context: tuple[str, str, str],
) -> tuple[Path, str, dict[str, str]]:
    """Write .mt_prompt.md and build command and environment for stage execution."""
    target_id = str(target_document.frontmatter["id"])
    prompt_text, _ = build_agent_prompt(worktree_path, agent_role, target_id)
    prompt_file = worktree_path / ".mt_prompt.md"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    command_template, environment_name, model_name = execution_context
    rendered = (
        command_template.replace("{model}", model_name)
        .replace("{task_id}", target_id)
        .replace("{agent_role}", agent_role)
        .replace("{prompt_file}", str(prompt_file))
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(worktree_path),
        "MT_AGENT_ROLE": agent_role,
        "MT_TASK_ID": target_id,
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
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
            code, timed_out = process.returncode, False
            out, err = process.stdout.strip(), process.stderr.strip()
        except subprocess.TimeoutExpired as exc:
            code, timed_out = -1, True
            out = (exc.stdout or b"").decode("utf-8", errors="replace").strip()
            err = (exc.stderr or b"").decode("utf-8", errors="replace").strip()
        details = {
            "command": rendered,
            "return_code": code,
            "timed_out": timed_out,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "stdout": out,
            "stderr": err,
        }
        record_task_event(
            worktree_path,
            target_id,
            "agent_invocation",
            details,
            execution_context,
            agent_role,
        )
    finally:
        prompt_file.unlink(missing_ok=True)
    return _detect_stage_changes(worktree_path, before, target_id)


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
    if agent_role not in permissions.get("agents", {}):
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
        ctx = resolve_task_execution(
            worktree_path, target_document, options, agent_role
        )
        exec_ctx = (ctx[0] or "", ctx[1], ctx[2])
        changed = (
            _run_stage_subprocess(worktree_path, agent_role, target_document, exec_ctx)
            if ctx[0]
            else []
        )
        task_arg = target_id if agent_role == "worker-agent" else None
        request = GateRequest(
            repository_root, worktree_path, agent_role, task_arg, None, changed
        )
        outcome = evaluate_merge_gate(request)
        merge_worktree_task_logs(repository_root, worktree_path, target_id)
        record_task_event(
            repository_root,
            target_id,
            "merge_gate",
            {"passed": outcome.passed, "changed_files": list(changed)},
            exec_ctx,
            agent_role,
        )
        return _finalize_stage_outcome(request, target_id, outcome)
    finally:
        remove_worktree(repository_root, worktree_path)


def _dispatch_routed_escalation(
    repository_root: Path,
    pipeline: dict[str, Any],
    options: tuple[str | None, str | None, str | None],
) -> tuple[list[str], list[Finding]] | None:
    """Dispatch the first routed_to_agent Escalation in an isolated Worktree."""
    for esc_id, document in sorted(load_artifacts_by_id(repository_root).items()):
        if (
            document.artifact_type != "ESC"
            or document.frontmatter.get("status") != "routed_to_agent"
        ):
            continue
        category = str(document.frontmatter.get("reason_category", "ambiguity"))
        routes: dict[str, Any] = pipeline.get("escalation_routes", {})
        actor = str(
            routes.get(category, {}).get(
                "target_actor", CATEGORY_ROUTES.get(category, ("human",))[0]
            )
        )
        if actor == "human":
            update_artifact_frontmatter(
                repository_root / document.path, {"status": "awaiting_human"}
            )
            commit_traceable_change(
                repository_root,
                [document.path],
                f"{esc_id}: Route escalation to human [traces: {esc_id}]",
            )
            return None
        produced, findings = run_agent_stage(repository_root, actor, esc_id, options)
        next_state = "awaiting_human" if findings else "resolved"
        update_artifact_frontmatter(
            repository_root / document.path,
            {"status": next_state, "resolved_by": produced[0] if produced else esc_id},
        )
        commit_traceable_change(
            repository_root,
            [document.path],
            f"{esc_id}: Resolve escalation via {actor} [traces: {esc_id}]",
        )
        return produced, findings
    return None


def _step_declarative_stage(
    repository_root: Path,
    stage: dict[str, Any],
    target_id: str,
    options: tuple[str | None, str | None, str | None],
) -> tuple[list[str], list[Finding]]:
    """Execute one matched stage and apply its configured approval_gate."""
    role = str(stage.get("agent_role", ""))
    gate = str(stage.get("approval_gate", "human"))
    if role == "worker-agent":
        return run_scheduled_tasks(
            repository_root, 1, options[0], options[1], options[2] or "agy"
        )
    produced, findings = run_agent_stage(repository_root, role, target_id, options)
    if findings or gate == "human":
        return produced, findings
    for artifact_id in list(produced):
        if gate == "review-agent":
            rev_ids, rev_findings = run_agent_stage(
                repository_root, "review-agent", artifact_id, options
            )
            if rev_findings or not rev_ids:
                return produced, rev_findings
            verdict_findings = evaluate_review_verdict(
                repository_root, artifact_id, rev_ids[0]
            )
            if verdict_findings:
                return produced, verdict_findings
            produced.extend(rev_ids)
        approve_stage_artifact(repository_root, artifact_id)
    return produced, []


def run_declarative_pipeline(
    repository_root: Path,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
) -> tuple[list[str], list[Finding]]:
    """Step through policy/pipeline.yaml stages and auto-routed Escalations."""
    pipeline = load_pipeline_policy(repository_root)
    max_steps = int(pipeline.get("execution_bounds", {}).get("max_steps_per_run", 20))
    stages: list[dict[str, Any]] = list(pipeline.get("stages", []))
    completed: list[str] = []
    for _ in range(max(1, max_steps)):
        matched = next(
            (
                (stage, target)
                for stage in stages
                if (target := find_actionable_stage_target(repository_root, stage))
                is not None
            ),
            None,
        )
        if matched is None or matched[0].get("trigger_type") in {"SPEC", "TASK"}:
            esc_result = _dispatch_routed_escalation(repository_root, pipeline, options)
            if esc_result is not None:
                produced, findings = esc_result
                if findings:
                    return completed, findings
                completed.extend(produced)
                continue
        if matched is None:
            break
        produced, findings = _step_declarative_stage(
            repository_root, matched[0], matched[1], options
        )
        if findings or not produced:
            return completed, findings
        completed.extend(produced)
    return completed, []
