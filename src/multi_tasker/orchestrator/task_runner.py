"""Parallel Worktree Task execution runner (`mt run`)."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shlex
import subprocess
import threading
import time

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import load_artifacts_by_id, update_artifact_frontmatter
from multi_tasker.orchestrator.documentation_generator import (
    write_repository_documentation,
)
from multi_tasker.orchestrator.interaction_logger import (
    merge_worktree_task_logs,
    record_task_event,
)
from multi_tasker.orchestrator.merge_gate import (
    GateOutcome,
    GateRequest,
    evaluate_merge_gate,
)
from multi_tasker.orchestrator.prompt_builder import (
    prepare_worker_invocation,
    resolve_task_execution,
)
from multi_tasker.orchestrator.router import route_escalation
from multi_tasker.orchestrator.scheduler import select_parallel_batch
from multi_tasker.orchestrator.worktree import (
    commit_traceable_change,
    create_worktree,
    format_task_commit_message,
    merge_worktree_files,
    remove_worktree,
)


def _list_escalations(worktree_path: Path) -> set[str]:
    """Return relative paths of all ESC-*.md files inside worktree_path."""
    escalation_directory = worktree_path / "artifacts" / "escalations"
    if not escalation_directory.exists():
        return set()
    return {
        file_path.relative_to(worktree_path).as_posix()
        for file_path in escalation_directory.glob("ESC-*.md")
    }


def _collect_worktree_changes(
    worktree_path: Path,
    task_id: str,
    write_files: list[str],
    existing_escalations: set[str],
) -> list[str]:
    """Collect modified relative file paths in worktree_path after agent execution."""
    if (worktree_path / ".git").exists():
        task_relative_path = f"artifacts/tasks/{task_id}.md"
        return [
            path
            for path in get_git_changed_files(worktree_path)
            if path != task_relative_path
        ]
    new_escalations = sorted(_list_escalations(worktree_path) - existing_escalations)
    return new_escalations if new_escalations else write_files


def _run_worker_subprocess(
    worktree_path: Path,
    rendered_command: str,
    environment: dict[str, str],
    timeout_seconds: float,
) -> dict[str, object]:
    """Execute worker subprocess and return structured outcome details."""
    started = time.monotonic()
    try:
        process = subprocess.run(
            shlex.split(rendered_command),
            cwd=worktree_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
        elapsed = int((time.monotonic() - started) * 1000)
        stdout_text, stderr_text = process.stdout.strip(), process.stderr.strip()
        return_code, timed_out = process.returncode, False
    except subprocess.TimeoutExpired:
        elapsed = int((time.monotonic() - started) * 1000)
        stdout_text, stderr_text, return_code, timed_out = "", "", -1, True
    return {
        "command": rendered_command,
        "return_code": return_code,
        "timed_out": timed_out,
        "duration_ms": elapsed,
        "stdout": stdout_text,
        "stderr": stderr_text,
    }


def _invoke_agent_in_worktree(
    worktree_path: Path,
    document: ArtifactDocument,
    execution_context: tuple[str, str, str],
    timeout_seconds: float = 300.0,
) -> list[str]:
    """Execute resolved command inside worktree_path and return modified paths."""
    task_id = str(document.frontmatter["id"])
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    existing_escalations = _list_escalations(worktree_path)
    prompt_file = worktree_path / ".mt_prompt.md"
    rendered_command, environment = prepare_worker_invocation(
        worktree_path, document, prompt_file, execution_context
    )
    try:
        details = _run_worker_subprocess(
            worktree_path, rendered_command, environment, timeout_seconds
        )
        record_task_event(
            worktree_path, task_id, "agent_invocation", details, execution_context
        )
    finally:
        prompt_file.unlink(missing_ok=True)
    return _collect_worktree_changes(
        worktree_path, task_id, write_files, existing_escalations
    )


def _finalize_task_outcome(
    repository_root: Path,
    worktree_path: Path,
    document: ArtifactDocument,
    outcome: GateOutcome,
    changed_files: list[str],
) -> list[Finding]:
    """Apply passing Worktree changes or route Escalation under merge lock."""
    absolute_task = repository_root / document.path
    task_id = str(document.frontmatter["id"])
    if outcome.escalated and outcome.escalation_path:
        merge_worktree_files(repository_root, worktree_path, [outcome.escalation_path])
        route = route_escalation(repository_root, outcome.escalation_path)
        update_artifact_frontmatter(
            repository_root / outcome.escalation_path, {"status": route.next_status}
        )
        update_artifact_frontmatter(absolute_task, {"status": "blocked"})
        commit_subject = (
            f"{route.escalation_id}: Escalate {task_id} to "
            f"{route.target_actor} ({route.action}) [traces: {task_id}]"
        )
        commit_traceable_change(
            repository_root, [document.path, outcome.escalation_path], commit_subject
        )
        message = f"Task escalated to '{route.target_actor}' ({route.action})."
        return [Finding(outcome.escalation_path, 1, "GATE_TASK_ESCALATED", message)]
    if outcome.passed:
        merge_worktree_files(repository_root, worktree_path, changed_files)
        update_artifact_frontmatter(absolute_task, {"status": "done"})
        commit_traceable_change(
            repository_root,
            [document.path, *changed_files],
            format_task_commit_message(document),
        )
        return []
    return outcome.findings


def _prepare_batch_worktrees(
    repository_root: Path, max_workers: int
) -> list[tuple[ArtifactDocument, Path]]:
    """Select parallel Task batch and create an in_progress Worktree for each Task."""
    batch, _ = select_parallel_batch(repository_root)
    by_identifier = load_artifacts_by_id(repository_root)
    selected = [
        by_identifier[task_id]
        for task_id in batch[: max(1, max_workers)]
        if task_id in by_identifier
    ]
    prepared: list[tuple[ArtifactDocument, Path]] = []
    for document in selected:
        task_id = str(document.frontmatter["id"])
        worktree_path = create_worktree(repository_root, task_id)
        update_artifact_frontmatter(
            worktree_path / document.path, {"status": "in_progress"}
        )
        prepared.append((document, worktree_path))
    return prepared


def _resolve_and_invoke_worktree(
    worktree_path: Path,
    document: ArtifactDocument,
    execution_options: tuple[str | None, str | None, str | None],
) -> tuple[list[str], tuple[str | None, str, str]]:
    """Resolve execution context and invoke worker command when configured."""
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    context = resolve_task_execution(worktree_path, document, execution_options)
    if context[0] and (
        execution_options[0]
        or execution_options[2]
        or document.frontmatter.get("execution_environment")
    ):
        changed = _invoke_agent_in_worktree(
            worktree_path, document, (context[0], context[1], context[2])
        )
        return changed, context
    return write_files, context


def _record_gate_and_merge_logs(
    repository_root: Path,
    worktree_path: Path,
    task_id: str,
    outcome: GateOutcome,
    execution_data: tuple[list[str], tuple[str | None, str, str]],
) -> None:
    """Merge Worktree Task logs and append MergeGate outcome event on BaseBranch."""
    changed, execution_context = execution_data
    merge_worktree_task_logs(repository_root, worktree_path, task_id)
    details = {
        "passed": outcome.passed,
        "escalated": outcome.escalated,
        "escalation_path": outcome.escalation_path,
        "changed_files": list(changed),
        "findings": [item.format() for item in outcome.findings],
    }
    record_task_event(
        repository_root, task_id, "merge_gate", details, execution_context
    )


def _execute_single_task(
    repository_root: Path,
    document: ArtifactDocument,
    worktree_path: Path,
    execution_options: tuple[str | None, str | None, str | None],
    merge_lock: threading.Lock,
) -> list[Finding]:
    """Run MergeGate verification for a single Task in an isolated Worktree."""
    task_id = str(document.frontmatter["id"])
    verification = str(document.frontmatter.get("verification_cmd", "")) or None
    try:
        changed, execution_context = _resolve_and_invoke_worktree(
            worktree_path, document, execution_options
        )
        outcome = evaluate_merge_gate(
            GateRequest(
                repository_root,
                worktree_path,
                "worker-agent",
                task_id,
                verification,
                changed,
            )
        )
        with merge_lock:
            _record_gate_and_merge_logs(
                repository_root,
                worktree_path,
                task_id,
                outcome,
                (changed, execution_context),
            )
            return _finalize_task_outcome(
                repository_root, worktree_path, document, outcome, changed
            )
    finally:
        with merge_lock:
            remove_worktree(repository_root, worktree_path)


def _execute_wave(
    repository_root: Path,
    prepared: list[tuple[ArtifactDocument, Path]],
    max_workers: int,
    execution_options: tuple[str | None, str | None, str | None],
) -> tuple[list[str], list[Finding]]:
    """Execute one conflict-free wave of prepared Worktrees in parallel."""
    merge_lock, completed, findings = threading.Lock(), [], []
    with ThreadPoolExecutor(max_workers=max(1, max_workers)) as executor:
        futures = [
            (
                str(document.frontmatter["id"]),
                executor.submit(
                    _execute_single_task,
                    repository_root,
                    document,
                    worktree_path,
                    execution_options,
                    merge_lock,
                ),
            )
            for document, worktree_path in prepared
        ]
        for task_id, future in futures:
            result = future.result()
            findings.extend(result) if result else completed.append(task_id)
    return completed, findings


def run_scheduled_tasks(
    repository_root: Path,
    max_workers: int = 1,
    agent_command: str | None = None,
    model_override: str | None = None,
    environment_override: str | None = None,
) -> tuple[list[str], list[Finding]]:
    """Execute successive conflict-free waves of eligible Tasks until done or error."""
    execution_options = (agent_command, model_override, environment_override)
    completed: list[str] = []
    findings: list[Finding] = []
    while True:
        prepared = _prepare_batch_worktrees(repository_root, max_workers)
        if not prepared:
            break
        wave_completed, wave_findings = _execute_wave(
            repository_root, prepared, max_workers, execution_options
        )
        completed.extend(wave_completed)
        findings.extend(wave_findings)
        if wave_findings or not wave_completed:
            break
    write_repository_documentation(repository_root)
    return completed, findings
