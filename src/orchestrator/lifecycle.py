"""End-to-end Orchestrator lifecycle commands (`initialize`, `intent`, `approve`)."""

from datetime import UTC, datetime
from pathlib import Path
import shutil
import subprocess

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
from src.orchestrator.scheduler import compute_dirty_subgraph


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
    """Approve a Requirement, Specification, or Decision and mark downstream dirty."""
    document = load_artifacts_by_id(repository_root).get(artifact_id)
    if document is None or document.artifact_type not in {"REQ", "SPEC", "DEC"}:
        message = (
            f"Approvable Requirement, Specification, or Decision '{artifact_id}' "
            "not found."
        )
        return [Finding(artifact_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    errors = _check_transition(repository_root, document, "approved")
    if errors:
        return errors
    findings = run_checks(
        repository_root, ["glossary", "schemas"], target_paths=[document.path]
    )
    if findings:
        return findings
    update_artifact_frontmatter(repository_root / document.path, {"status": "approved"})
    _mark_dirty_downstream(repository_root, artifact_id)
    return []


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
