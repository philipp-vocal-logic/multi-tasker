"""End-to-end Orchestrator lifecycle commands (`initialize`, `intent`, `approve`)."""

from datetime import UTC, datetime
from pathlib import Path
import shutil
import subprocess

import yaml

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.checkers.runner import run_checks
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import (
    ARTIFACT_DIRECTORY_TO_TYPE,
    load_artifacts_by_id,
    load_yaml_file,
    update_artifact_frontmatter,
)
from multi_tasker.orchestrator.router import check_transition
from multi_tasker.orchestrator.documentation_generator import (
    generate_external_agents_guide,
    write_repository_documentation,
)
from multi_tasker.orchestrator.scheduler import compute_dirty_subgraph
from multi_tasker.orchestrator.worktree import commit_traceable_change


DEFAULT_GITIGNORE_ENTRIES = (
    ".worktrees/",
    ".report/",
    ".mt_prompt.md",
    "__pycache__/",
    "*.py[cod]",
    ".pytest_cache/",
)


VALID_PRESETS = ("python", "multi-tasker")

DEFAULT_PYTHON_ARCHITECTURE: dict[str, object] = {
    "version": 1,
    "dependency_rules": {
        "forbid_circular_imports": True,
        "forbid_src_importing_tests": True,
    },
    "allowed_third_party_packages": ["yaml", "jsonschema", "pytest", "multi_tasker"],
    "layers": [
        {
            "name": "domain",
            "paths": ["src/domain/**", "src/*.py"],
            "allowed_internal_imports": ["src.domain", "domain"],
            "forbidden_internal_imports": ["src.services", "src.cli", "tests"],
        },
        {
            "name": "services",
            "paths": ["src/services/**", "src/application/**"],
            "allowed_internal_imports": [
                "src.domain",
                "src.services",
                "src.application",
                "domain",
                "services",
                "application",
            ],
            "forbidden_internal_imports": ["src.cli", "tests"],
        },
        {
            "name": "cli",
            "paths": ["src/cli/**"],
            "allowed_internal_imports": [
                "src",
                "domain",
                "services",
                "application",
                "cli",
            ],
            "forbidden_internal_imports": ["tests"],
        },
        {
            "name": "tests",
            "paths": ["tests/**"],
            "allowed_internal_imports": [
                "src",
                "domain",
                "services",
                "application",
                "cli",
                "tests",
            ],
            "forbidden_internal_imports": [],
        },
    ],
}


def _scaffold_default_policies_and_gitignore(
    repository_root: Path, preset: str = "python"
) -> None:
    """Copy missing default policy/*.yaml templates and ensure .gitignore entries."""
    packaged = Path(__file__).resolve().parents[1] / "policy_templates"
    template_directory = (
        packaged
        if packaged.is_dir()
        else Path(__file__).resolve().parents[3] / "policy"
    )
    target_policy_directory = repository_root / "policy"
    if template_directory.is_dir():
        for template_path in sorted(template_directory.glob("*.yaml")):
            destination = target_policy_directory / template_path.name
            if not destination.exists():
                content = (
                    yaml.safe_dump(DEFAULT_PYTHON_ARCHITECTURE, sort_keys=False)
                    if template_path.name == "architecture.yaml" and preset == "python"
                    else template_path.read_text(encoding="utf-8")
                )
                destination.write_text(content, encoding="utf-8")
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


def initialize_repository(
    repository_root: Path, preset: str = "python"
) -> list[Finding]:
    """Initialize policy/, artifacts/ subdirectories, and a Git repository."""
    if preset not in VALID_PRESETS:
        message = f"Unknown preset '{preset}' (expected: {', '.join(VALID_PRESETS)})."
        return [Finding("policy/architecture.yaml", 1, "CLI_INVALID_PRESET", message)]
    (repository_root / "policy").mkdir(parents=True, exist_ok=True)
    for folder in ARTIFACT_DIRECTORY_TO_TYPE:
        (repository_root / "artifacts" / folder).mkdir(parents=True, exist_ok=True)
    _scaffold_default_policies_and_gitignore(repository_root, preset)
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


def _sync_upstream_intents(
    repository_root: Path,
    changed_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> None:
    """Update upstream Intents to processing or processed based on all linked REQs."""
    for upstream_id in (
        str(item) for item in changed_document.frontmatter.get("traces_to", [])
    ):
        intent_doc = by_identifier.get(upstream_id)
        if not intent_doc or intent_doc.frontmatter.get("status") not in {
            "open",
            "processing",
        }:
            continue
        all_approved = all(
            doc.frontmatter.get("status") in {"approved", "deprecated"}
            for doc in by_identifier.values()
            if doc.artifact_type == "REQ"
            and upstream_id
            in {str(item) for item in doc.frontmatter.get("traces_to", [])}
        )
        next_status = "processed" if all_approved else "processing"
        update_artifact_frontmatter(
            repository_root / intent_doc.path, {"status": next_status}
        )


def _deprecate_superseded_requirements(
    repository_root: Path,
    changed_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> None:
    """Deprecate superseded Requirements and exclusively linked Specifications."""
    for req_id in (
        str(item) for item in changed_document.frontmatter.get("supersedes", [])
    ):
        req_doc = by_identifier.get(req_id)
        if req_doc and req_doc.frontmatter.get("status") == "approved":
            update_artifact_frontmatter(
                repository_root / req_doc.path, {"status": "deprecated"}
            )
            req_doc.frontmatter["status"] = "deprecated"
    deprecated_reqs = {
        aid
        for aid, doc in by_identifier.items()
        if doc.artifact_type == "REQ" and doc.frontmatter.get("status") == "deprecated"
    }
    for doc in by_identifier.values():
        refs = {str(ref) for ref in doc.frontmatter.get("traces_to", [])}
        if (
            doc.artifact_type == "SPEC"
            and doc.frontmatter.get("status") == "approved"
            and refs
            and refs <= deprecated_reqs
        ):
            update_artifact_frontmatter(
                repository_root / doc.path, {"status": "deprecated"}
            )


def _mark_dirty_downstream(repository_root: Path, changed_id: str) -> list[str]:
    """Transition downstream SPEC/TASK to needs_update and sync upstream Intents."""
    by_identifier = load_artifacts_by_id(repository_root)
    changed_document = by_identifier.get(changed_id)
    if changed_document and changed_document.artifact_type == "REQ":
        _deprecate_superseded_requirements(
            repository_root, changed_document, by_identifier
        )
        _sync_upstream_intents(repository_root, changed_document, by_identifier)
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
    errors = check_transition(repository_root, document, "approved")
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
