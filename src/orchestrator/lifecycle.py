"""End-to-end Orchestrator lifecycle commands (`initialize`, `intent`, `approve`)."""

from concurrent.futures import ThreadPoolExecutor
import contextlib
from datetime import UTC, datetime
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import threading

from src.checkers.common import get_git_changed_files
from src.checkers.runner import run_checks
from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import (
    ARTIFACT_DIRECTORY_TO_TYPE,
    load_artifacts_by_id,
    load_state_transitions,
    update_artifact_frontmatter,
)
from src.orchestrator.documentation_generator import (
    write_repository_documentation,
)
from src.orchestrator.merge_gate import GateOutcome, GateRequest, evaluate_merge_gate
from src.orchestrator.prompt_builder import build_agent_prompt, resolve_task_execution
from src.orchestrator.router import route_escalation
from src.orchestrator.scheduler import compute_dirty_subgraph, select_parallel_batch
from src.orchestrator.worktree import (
    commit_traceable_change,
    create_worktree,
    format_task_commit_message,
    merge_worktree_files,
    remove_worktree,
)


def initialize_repository(repository_root: Path) -> list[Finding]:
    """Initialize policy/, artifacts/ subdirectories, and a Git repository."""
    (repository_root / "policy").mkdir(parents=True, exist_ok=True)
    for folder in ARTIFACT_DIRECTORY_TO_TYPE:
        (repository_root / "artifacts" / folder).mkdir(parents=True, exist_ok=True)
    if not (repository_root / ".git").exists() and shutil.which("git"):
        subprocess.run(
            ["git", "init", "-q"], cwd=repository_root, capture_output=True, check=False
        )
    write_repository_documentation(repository_root)
    return []


def _next_intent_id(intents_directory: Path) -> str:
    """Compute the next sequential INT-NNN identifier."""
    numbers = [
        int(file_path.stem.split("-", maxsplit=1)[-1])
        for file_path in intents_directory.glob("INT-*.md")
        if file_path.stem.split("-", maxsplit=1)[-1].isdigit()
    ]
    return f"INT-{max(numbers, default=0) + 1:03d}"


def _resolve_intent_body(repository_root: Path, text_or_file: str) -> str:
    """Resolve raw intent text or read from a single-line file path."""
    stripped = text_or_file.strip()
    if "\n" not in stripped and len(stripped) < 240:
        for candidate in (Path(stripped), repository_root / stripped):
            if candidate.is_file():
                return candidate.read_text(encoding="utf-8").strip()
    return stripped


def create_intent(
    repository_root: Path, text_or_file: str, timestamp: str | None = None
) -> str:
    """Create a new INT-NNN.md artifact from raw text or a file path."""
    intents_directory = repository_root / "artifacts" / "intents"
    intents_directory.mkdir(parents=True, exist_ok=True)
    intent_id = _next_intent_id(intents_directory)
    body = _resolve_intent_body(repository_root, text_or_file)
    created_at = timestamp or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    content = (
        f'---\nid: {intent_id}\nstatus: open\ncreated_at: "{created_at}"\n---\n{body}\n'
    )
    (intents_directory / f"{intent_id}.md").write_text(content, encoding="utf-8")
    write_repository_documentation(repository_root)
    return intent_id


def _check_transition(
    repository_root: Path, document: ArtifactDocument, target_state: str
) -> list[Finding]:
    """Validate artifact status transition against schemas or permissions policy."""
    current_state = str(document.frontmatter.get("status", ""))
    if not current_state:
        return []
    transitions = load_state_transitions(repository_root)
    allowed = transitions.get(document.artifact_type, {}).get(current_state)
    if isinstance(allowed, set) and target_state not in allowed:
        message = f"Invalid state transition '{current_state}' -> '{target_state}'."
        return [Finding(document.path, 1, "PERM_INVALID_STATE_TRANSITION", message)]
    return []


def _mark_dirty_downstream(repository_root: Path, changed_id: str) -> list[str]:
    """Transition downstream SPEC/TASK to needs_update and upstream INT to processed."""
    by_identifier = load_artifacts_by_id(repository_root)
    changed_document = by_identifier.get(changed_id)
    if changed_document and changed_document.artifact_type == "REQ":
        for upstream_id in changed_document.frontmatter.get("traces_to", []):
            intent_document = by_identifier.get(str(upstream_id))
            if intent_document and intent_document.frontmatter.get("status") in {
                "open",
                "processing",
            }:
                update_artifact_frontmatter(
                    repository_root / intent_document.path, {"status": "processed"}
                )
    dirty_ids = compute_dirty_subgraph(repository_root, changed_id)
    for artifact_id in dirty_ids:
        document = by_identifier.get(artifact_id)
        if document and document.frontmatter.get("status") in {"approved", "done"}:
            update_artifact_frontmatter(
                repository_root / document.path, {"status": "needs_update"}
            )
    write_repository_documentation(repository_root)
    return dirty_ids


def approve_artifact(repository_root: Path, artifact_id: str) -> list[Finding]:
    """Approve a Requirement or Decision and mark downstream artifacts dirty."""
    document = load_artifacts_by_id(repository_root).get(artifact_id)
    if document is None or document.artifact_type not in {"REQ", "DEC"}:
        message = f"Approvable Requirement or Decision '{artifact_id}' not found."
        return [Finding(artifact_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    errors = _check_transition(repository_root, document, "approved")
    if errors:
        return errors
    update_artifact_frontmatter(repository_root / document.path, {"status": "approved"})
    findings = run_checks(
        repository_root, ["glossary", "schemas"], target_paths=[document.path]
    )
    if not findings:
        _mark_dirty_downstream(repository_root, artifact_id)
    return findings


def resolve_escalation(
    repository_root: Path, escalation_id: str, resolved_by: str
) -> list[Finding]:
    """Resolve an Escalation with a Decision or Task and propagate dirty flags."""
    by_identifier = load_artifacts_by_id(repository_root)
    escalation = by_identifier.get(escalation_id)
    resolution = by_identifier.get(resolved_by)
    if escalation is None or escalation.artifact_type != "ESC":
        message = f"Escalation '{escalation_id}' not found."
        return [Finding(escalation_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    if resolution is None or resolution.artifact_type not in {"DEC", "TASK"}:
        message = f"Resolving Decision or Task '{resolved_by}' not found."
        return [Finding(resolved_by, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    errors = _check_transition(repository_root, escalation, "resolved")
    if (
        resolution.artifact_type == "DEC"
        and resolution.frontmatter.get("status") != "approved"
    ):
        errors.extend(_check_transition(repository_root, resolution, "approved"))
    if errors:
        return errors
    findings = run_checks(
        repository_root, ["glossary", "schemas"], target_paths=[resolution.path]
    )
    if findings:
        return findings
    if resolution.artifact_type == "DEC":
        update_artifact_frontmatter(
            repository_root / resolution.path, {"status": "approved"}
        )
    update_artifact_frontmatter(
        repository_root / escalation.path,
        {"status": "resolved", "resolved_by": resolved_by},
    )
    _mark_dirty_downstream(repository_root, resolved_by)
    return []


def _list_escalations(worktree_path: Path) -> set[str]:
    """Return relative paths of all ESC-*.md files inside worktree_path."""
    escalation_directory = worktree_path / "artifacts" / "escalations"
    if not escalation_directory.exists():
        return set()
    return {
        file_path.relative_to(worktree_path).as_posix()
        for file_path in escalation_directory.glob("ESC-*.md")
    }


def _write_worktree_prompt_file(worktree_path: Path, task_id: str) -> Path:
    """Write synthesized worker-agent prompt into worktree_path/.mt_prompt.md."""
    prompt_text, _ = build_agent_prompt(worktree_path, "worker-agent", task_id)
    prompt_file = worktree_path / ".mt_prompt.md"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    return prompt_file


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


def _prepare_worker_invocation(
    task_id: str,
    write_files: list[str],
    prompt_file: Path,
    execution_context: tuple[str, str, str],
) -> tuple[str, dict[str, str]]:
    """Build rendered command string and subprocess environment for worker execution."""
    command_template, environment_name, model_name = execution_context
    rendered_command = (
        command_template.replace("{model}", model_name)
        .replace("{task_id}", task_id)
        .replace("{prompt_file}", str(prompt_file))
    )
    environment = {
        **os.environ,
        "MT_AGENT_ROLE": "worker-agent",
        "MT_TASK_ID": task_id,
        "MT_WRITE_FILES": ",".join(write_files),
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
    }
    return rendered_command, environment


def _invoke_agent_in_worktree(
    worktree_path: Path,
    task_id: str,
    write_files: list[str],
    execution_context: tuple[str, str, str],
    timeout_seconds: float = 300.0,
) -> list[str]:
    """Execute resolved command inside worktree_path and return modified paths."""
    existing_escalations = _list_escalations(worktree_path)
    prompt_file = _write_worktree_prompt_file(worktree_path, task_id)
    rendered_command, environment = _prepare_worker_invocation(
        task_id, write_files, prompt_file, execution_context
    )
    try:
        with contextlib.suppress(subprocess.TimeoutExpired):
            subprocess.run(
                shlex.split(rendered_command),
                cwd=worktree_path,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
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
    task_id = str(document.frontmatter.get("id", "TASK-000"))
    previous_status = str(document.frontmatter.get("status", "planned"))
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
    update_artifact_frontmatter(absolute_task, {"status": previous_status})
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
) -> list[str]:
    """Resolve execution context and invoke worker command when configured."""
    task_id = str(document.frontmatter["id"])
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    execution_context = resolve_task_execution(
        worktree_path, document, execution_options
    )
    if (
        execution_options[0]
        or execution_options[2]
        or document.frontmatter.get("execution_environment")
    ):
        return _invoke_agent_in_worktree(
            worktree_path, task_id, write_files, execution_context
        )
    return write_files


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
        changed = _resolve_and_invoke_worktree(
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
            return _finalize_task_outcome(
                repository_root, worktree_path, document, outcome, changed
            )
    finally:
        with merge_lock:
            remove_worktree(repository_root, worktree_path)


def run_scheduled_tasks(
    repository_root: Path,
    max_workers: int = 1,
    agent_command: str | None = None,
    model_override: str | None = None,
    environment_override: str | None = None,
) -> tuple[list[str], list[Finding]]:
    """Execute conflict-free batch of eligible Tasks up to max_workers."""
    prepared = _prepare_batch_worktrees(repository_root, max_workers)
    if not prepared:
        write_repository_documentation(repository_root)
        return [], []
    execution_options = (agent_command, model_override, environment_override)
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
    write_repository_documentation(repository_root)
    return completed, findings
