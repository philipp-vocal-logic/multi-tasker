"""End-to-end Orchestrator lifecycle commands (`initialize`, `intent`, `approve`)."""

from datetime import UTC, datetime
from pathlib import Path
import shutil
import subprocess

import yaml

from src.checkers.common import get_git_changed_files
from src.checkers.runner import run_checks
from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import (
    ARTIFACT_DIRECTORY_TO_TYPE,
    load_artifacts_by_id,
    load_pipeline_policy,
    load_state_transitions,
    load_yaml_file,
    update_artifact_frontmatter,
)
from src.orchestrator.documentation_generator import (
    generate_external_agents_guide,
    write_repository_documentation,
)
from src.orchestrator.scheduler import compute_dirty_subgraph
from src.orchestrator.worktree import commit_traceable_change


DEFAULT_GITIGNORE_ENTRIES = (
    ".worktrees/",
    ".report/",
    ".mt_prompt.md",
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
)


def _scaffold_default_policies_and_gitignore(repository_root: Path) -> None:
    """Copy missing default policy/*.yaml templates and ensure .gitignore entries."""
    template_directory = Path(__file__).resolve().parents[2] / "policy"
    target_policy_directory = repository_root / "policy"
    if template_directory.is_dir():
        for template_path in sorted(template_directory.glob("*.yaml")):
            destination = target_policy_directory / template_path.name
            if not destination.exists():
                destination.write_text(
                    template_path.read_text(encoding="utf-8"), encoding="utf-8"
                )
    gitignore_path = repository_root / ".gitignore"
    existing_text = (
        gitignore_path.read_text(encoding="utf-8") if gitignore_path.is_file() else ""
    )
    existing_lines = {line.strip() for line in existing_text.splitlines()}
    missing = [
        entry for entry in DEFAULT_GITIGNORE_ENTRIES if entry not in existing_lines
    ]
    if missing:
        prefix = (
            existing_text
            if not existing_text or existing_text.endswith("\n")
            else f"{existing_text}\n"
        )
        gitignore_path.write_text(
            f"{prefix}" + "\n".join(missing) + "\n", encoding="utf-8"
        )
    agents_path = repository_root / "AGENTS.md"
    if not agents_path.exists():
        agents_path.write_text(generate_external_agents_guide(), encoding="utf-8")


def initialize_repository(repository_root: Path) -> list[Finding]:
    """Initialize policy/, artifacts/ subdirectories, and a Git repository."""
    (repository_root / "policy").mkdir(parents=True, exist_ok=True)
    for folder in ARTIFACT_DIRECTORY_TO_TYPE:
        (repository_root / "artifacts" / folder).mkdir(parents=True, exist_ok=True)
    _scaffold_default_policies_and_gitignore(repository_root)
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
        repository_root,
        ["glossary", "schemas", "traceability"],
        target_paths=[document.path],
    )
    if findings:
        return findings
    update_artifact_frontmatter(repository_root / document.path, {"status": "approved"})
    _mark_dirty_downstream(repository_root, artifact_id)
    return []


def approve_stage_artifact(repository_root: Path, artifact_id: str) -> None:
    """Transition REQ/SPEC/DEC to approved or TASK to ready after stage gate."""
    document = load_artifacts_by_id(repository_root).get(artifact_id)
    if document is not None and document.artifact_type == "TASK":
        update_artifact_frontmatter(
            repository_root / document.path, {"status": "ready"}
        )
    else:
        approve_artifact(repository_root, artifact_id)
    changed = get_git_changed_files(repository_root)
    subject = (
        f"{artifact_id}: Approve stage artifact {artifact_id} [traces: {artifact_id}]"
    )
    commit_traceable_change(repository_root, changed, subject)


def _create_review_escalation(
    repository_root: Path, artifact_id: str, rev_path: str
) -> list[Finding]:
    """Create an awaiting_human review_exhausted Escalation and block artifact_id."""
    by_id = load_artifacts_by_id(repository_root)
    esc_nums = [
        int(key.split("-")[1])
        for key in by_id
        if key.startswith("ESC-") and key.split("-")[1].isdigit()
    ]
    esc_id = f"ESC-{max(esc_nums, default=0) + 1:03d}"
    esc_rel = f"artifacts/escalations/{esc_id}.md"
    (repository_root / esc_rel).write_text(
        f"---\nid: {esc_id}\nsource_agent: orchestrator\n"
        f"task_or_stage: {artifact_id}\naffected_artifacts: [{artifact_id}]\n"
        "reason_category: review_exhausted\nstatus: awaiting_human\n"
        "resolved_by: null\n---\n"
        f"## Blocking Problem\nReview cycles exhausted for {artifact_id}.\n",
        encoding="utf-8",
    )
    target_doc = by_id.get(artifact_id)
    if target_doc is not None:
        update_artifact_frontmatter(
            repository_root / target_doc.path, {"status": "blocked"}
        )
    changed = [
        esc_rel,
        *([target_doc.path] if target_doc is not None else []),
    ]
    subject = (
        f"{esc_id}: Escalate {artifact_id} review [traces: {artifact_id}, {esc_id}]"
    )
    commit_traceable_change(repository_root, changed, subject)
    message = f"Review cycles exhausted for '{artifact_id}' ({esc_id})."
    return [Finding(rev_path, 1, "STAGE_REVIEW_EXHAUSTED", message)]


def evaluate_review_verdict(
    repository_root: Path, artifact_id: str, rev_id: str
) -> list[Finding]:
    """Check REV verdict for artifact_id and emit Finding or escalation on fail."""
    by_id = load_artifacts_by_id(repository_root)
    rev_doc = by_id.get(rev_id)
    if rev_doc is None or rev_doc.frontmatter.get("verdict") == "pass":
        return []
    fail_count = sum(
        1
        for doc in by_id.values()
        if doc.artifact_type == "REV"
        and doc.frontmatter.get("verdict") == "fail"
        and artifact_id
        in {str(item) for item in doc.frontmatter.get("target_artifacts", [])}
    )
    bounds = load_pipeline_policy(repository_root).get("execution_bounds", {})
    if fail_count >= int(bounds.get("max_review_cycles", 2)):
        return _create_review_escalation(repository_root, artifact_id, rev_doc.path)
    message = f"Review '{rev_id}' rejected '{artifact_id}'."
    return [Finding(rev_doc.path, 1, "STAGE_REVIEW_REJECTED", message)]


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
        repository_root,
        ["glossary", "schemas", "traceability"],
        target_paths=[resolution.path],
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


def bootstrap_evaluation_repository(repository_root: Path, intent_text: str) -> str:
    """Initialize a Git repository with auto INT gate and commit baseline INT-001."""
    initialize_repository(repository_root)
    pipeline_path = repository_root / "policy" / "pipeline.yaml"
    if pipeline_path.is_file():
        pipeline = load_yaml_file(pipeline_path)
        for stage in pipeline.get("stages", []):
            if stage.get("id") in {"intent_to_requirement", "specification_to_tasks"}:
                stage["approval_gate"] = "auto"
        pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    clean_path = repository_root / "policy" / "clean_code.yaml"
    if clean_path.is_file() and not (repository_root / "pyproject.toml").is_file():
        clean_policy = load_yaml_file(clean_path)
        clean_policy["linters"]["ruff"]["enabled"] = False
        clean_policy["linters"]["mypy"]["enabled"] = False
        clean_path.write_text(yaml.safe_dump(clean_policy), encoding="utf-8")
    intent_id = create_intent(repository_root, intent_text)
    commit_msg = f"{intent_id}: Bootstrap evaluation repo [traces: {intent_id}]"
    for git_cmd in (
        ["git", "config", "user.email", "mt@local"],
        ["git", "config", "user.name", "mt"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", commit_msg],
    ):
        subprocess.run(git_cmd, cwd=repository_root, capture_output=True, check=False)
    return intent_id
