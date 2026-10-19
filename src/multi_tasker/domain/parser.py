"""YAML and Markdown frontmatter parser and artifact repository utilities."""

from pathlib import Path
from typing import Any

import yaml

from multi_tasker.domain.models import ArtifactDocument, Finding, SectionSlice

ARTIFACT_DIRECTORY_TO_TYPE: dict[str, str] = {
    "intents": "INT",
    "requirements": "REQ",
    "specifications": "SPEC",
    "tasks": "TASK",
    "escalations": "ESC",
    "decisions": "DEC",
    "reviews": "REV",
}


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load a YAML file and return a dictionary."""
    raw_content = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw_content, dict):
        return raw_content
    return {}


def load_pipeline_policy(repository_root: Path) -> dict[str, Any]:
    """Load policy/pipeline.yaml if present, otherwise return an empty dictionary."""
    pipeline_path = repository_root / "policy" / "pipeline.yaml"
    if not pipeline_path.exists():
        return {}
    return load_yaml_file(pipeline_path)


def infer_artifact_type(relative_path: str) -> str:
    """Infer artifact type code (INT, REQ, etc.) from relative path."""
    parts = Path(relative_path).parts
    if len(parts) >= 2 and parts[0] == "artifacts":
        return ARTIFACT_DIRECTORY_TO_TYPE.get(parts[1], "UNKNOWN")
    stem = Path(relative_path).stem
    prefix = stem.split("-", maxsplit=1)[0]
    return prefix if prefix in ARTIFACT_DIRECTORY_TO_TYPE.values() else "UNKNOWN"


def parse_sections(body: str, body_start_line: int) -> dict[str, SectionSlice]:
    """Extract level-2 Markdown sections (## Heading) with line numbers."""
    sections: dict[str, SectionSlice] = {}
    current_name: str | None = None
    current_start = body_start_line
    buffer: list[str] = []
    for index, line in enumerate(body.splitlines(), start=body_start_line):
        if line.startswith("## "):
            if current_name is not None:
                sections[current_name] = SectionSlice(
                    current_name, current_start, "\n".join(buffer).strip()
                )
            current_name = line[3:].strip()
            current_start = index + 1
            buffer = []
        elif current_name is not None:
            buffer.append(line)
    if current_name is not None:
        sections[current_name] = SectionSlice(
            current_name, current_start, "\n".join(buffer).strip()
        )
    return sections


def _split_frontmatter(lines: list[str]) -> tuple[int, str, str] | None:
    """Split lines after HTML comments into frontmatter and body."""
    start_index = 0
    while start_index < len(lines) and (
        not lines[start_index].strip() or lines[start_index].strip().startswith("<!--")
    ):
        start_index += 1
    if start_index >= len(lines) or lines[start_index].strip() != "---":
        return None
    for end_index in range(start_index + 1, len(lines)):
        if lines[end_index].strip() == "---":
            frontmatter_text = "\n".join(lines[start_index + 1 : end_index])
            body_text = "\n".join(lines[end_index + 1 :])
            return end_index + 2, frontmatter_text, body_text
    return None


def parse_artifact_file(
    absolute_path: Path, relative_path: str
) -> tuple[ArtifactDocument | None, list[Finding]]:
    """Parse a Markdown artifact into ArtifactDocument or return syntax Findings."""
    lines = absolute_path.read_text(encoding="utf-8").splitlines()
    split_result = _split_frontmatter(lines)
    if split_result is None:
        message = "Missing YAML frontmatter delimited by '---'."
        return None, [Finding(relative_path, 1, "TRACE_FRONTMATTER_MISSING", message)]
    body_start, frontmatter_text, body_text = split_result
    try:
        frontmatter_data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as error:
        message = f"Invalid YAML frontmatter: {error}"
        return None, [Finding(relative_path, 1, "TRACE_YAML_INVALID", message)]
    if not isinstance(frontmatter_data, dict):
        message = "Frontmatter must be a YAML mapping."
        return None, [Finding(relative_path, 1, "TRACE_YAML_NOT_MAP", message)]
    artifact_type = infer_artifact_type(relative_path)
    sections = parse_sections(body_text, body_start)
    document = ArtifactDocument(
        relative_path, artifact_type, frontmatter_data, body_text, body_start, sections
    )
    return document, []


def load_all_artifacts(
    repository_root: Path,
) -> tuple[dict[str, ArtifactDocument], list[Finding]]:
    """Parse all Markdown artifacts under artifacts/ and index by id."""
    artifacts_root = repository_root / "artifacts"
    if not artifacts_root.exists():
        return {}, []
    by_identifier: dict[str, ArtifactDocument] = {}
    findings: list[Finding] = []
    for markdown_path in sorted(artifacts_root.rglob("*.md")):
        relative_path = markdown_path.relative_to(repository_root).as_posix()
        document, errors = parse_artifact_file(markdown_path, relative_path)
        findings.extend(errors)
        if document is not None and document.frontmatter.get("id"):
            by_identifier[str(document.frontmatter["id"])] = document
    return by_identifier, findings


def load_artifacts_by_id(repository_root: Path) -> dict[str, ArtifactDocument]:
    """Load all valid Markdown artifacts indexed by frontmatter id."""
    by_identifier, _ = load_all_artifacts(repository_root)
    return by_identifier


def update_artifact_frontmatter(absolute_path: Path, updates: dict[str, Any]) -> None:
    """Update frontmatter keys in a Markdown artifact while preserving its body."""
    document, _ = parse_artifact_file(absolute_path, absolute_path.name)
    if document is None:
        return
    merged = {**document.frontmatter, **updates}
    frontmatter_yaml = yaml.safe_dump(merged, sort_keys=False).strip()
    body = document.body.lstrip("\n")
    suffix = f"\n{body}\n" if body else "\n"
    absolute_path.write_text(f"---\n{frontmatter_yaml}\n---{suffix}", encoding="utf-8")


def load_state_transitions(
    repository_root: Path, fallback_policy: dict[str, Any] | None = None
) -> dict[str, dict[str, set[str]]]:
    """Extract state_transitions table from schemas or permissions policy."""
    schemas_path = repository_root / "policy" / "schemas.yaml"
    permissions_path = repository_root / "policy" / "permissions.yaml"
    source_policy = fallback_policy or {}
    if schemas_path.exists():
        source_policy = load_yaml_file(schemas_path)
    elif permissions_path.exists() and not source_policy:
        source_policy = load_yaml_file(permissions_path)
    fallback_transitions = (fallback_policy or {}).get("state_transitions", {})
    raw_transitions = source_policy.get("state_transitions", fallback_transitions)
    return {
        str(artifact_type): {
            str(source): {str(target) for target in targets}
            for source, targets in mapping.items()
        }
        for artifact_type, mapping in raw_transitions.items()
        if isinstance(mapping, dict)
    }


def _validate_pipeline_bounds(bounds: dict[str, Any]) -> bool:
    """Return True if execution_bounds values in policy/pipeline.yaml are valid."""
    max_steps = bounds.get("max_steps_per_run", 0)
    max_reroutes = bounds.get("max_auto_reroutes", -1)
    max_reviews = bounds.get("max_review_cycles", 1)
    return (
        isinstance(max_steps, int)
        and max_steps >= 1
        and isinstance(max_reroutes, int)
        and max_reroutes >= 0
        and isinstance(max_reviews, int)
        and max_reviews >= 1
    )


def _validate_pipeline_stages(stages: list[Any]) -> list[Finding]:
    """Validate stage definitions in policy/pipeline.yaml."""
    valid_gates = {"human", "review-agent", "auto"}
    for entry in stages:
        if not isinstance(entry, dict):
            message = "Invalid stage entry in policy/pipeline.yaml."
            return [
                Finding("policy/pipeline.yaml", 1, "PIPELINE_INVALID_STAGE", message)
            ]
        stage_id = str(entry.get("id", ""))
        trigger = str(entry.get("trigger_type", ""))
        states = entry.get("trigger_states", [])
        downstream = str(entry.get("downstream_type", ""))
        role = str(entry.get("agent_role", ""))
        gate = str(entry.get("approval_gate", ""))
        valid_states = isinstance(states, list) and bool(states)
        if not (
            stage_id
            and trigger
            and valid_states
            and downstream
            and role
            and gate in valid_gates
        ):
            message = f"Invalid pipeline stage '{stage_id}' in policy/pipeline.yaml."
            return [
                Finding("policy/pipeline.yaml", 1, "PIPELINE_INVALID_STAGE", message)
            ]
    return []


def validate_pipeline_policy(repository_root: Path) -> list[Finding]:
    """Validate execution_bounds, stages, and escalation_routes in pipeline.yaml."""
    pipeline = load_pipeline_policy(repository_root)
    if not pipeline:
        return []
    bounds: dict[str, Any] = pipeline.get("execution_bounds", {})
    if not _validate_pipeline_bounds(bounds):
        message = "Invalid execution_bounds in policy/pipeline.yaml."
        return [Finding("policy/pipeline.yaml", 1, "PIPELINE_INVALID_BOUNDS", message)]
    stage_findings = _validate_pipeline_stages(list(pipeline.get("stages", [])))
    if stage_findings:
        return stage_findings
    routes: dict[str, Any] = pipeline.get("escalation_routes", {})
    for category, route in routes.items():
        if not isinstance(route, dict) or not (
            category
            and route.get("target_actor")
            and route.get("next_status")
            and route.get("action")
        ):
            message = f"Invalid escalation route '{category}' in policy/pipeline.yaml."
            return [
                Finding("policy/pipeline.yaml", 1, "PIPELINE_INVALID_ROUTE", message)
            ]
    return []


ARTIFACT_TYPE_TO_DIRECTORY: dict[str, str] = {
    value: key for key, value in ARTIFACT_DIRECTORY_TO_TYPE.items()
}


def next_artifact_id(
    repository_root: Path,
    artifact_type: str,
    reserved_ids: set[str] | None = None,
) -> str:
    """Compute the next sequential PREFIX-NNN identifier for artifact_type."""
    existing = set(load_artifacts_by_id(repository_root)) | (reserved_ids or set())
    folder = ARTIFACT_TYPE_TO_DIRECTORY.get(artifact_type)
    if folder and (repository_root / "artifacts" / folder).is_dir():
        for file_path in (repository_root / "artifacts" / folder).glob(
            f"{artifact_type}-*.md"
        ):
            existing.add(file_path.stem)
    numbers = [
        int(identifier.split("-", maxsplit=1)[1])
        for identifier in existing
        if identifier.startswith(f"{artifact_type}-")
        and identifier.split("-", maxsplit=1)[1].isdigit()
    ]
    return f"{artifact_type}-{max(numbers, default=0) + 1:03d}"


def _rewrite_normalized_artifact(
    worktree_path: Path,
    relative_path: str,
    document: ArtifactDocument,
    id_mapping: dict[str, str],
) -> str:
    """Write renumbered artifact frontmatter and return its new relative path."""
    old_id = str(document.frontmatter.get("id", Path(relative_path).stem))
    new_id = id_mapping.get(old_id, old_id)
    updated_frontmatter = dict(document.frontmatter)
    updated_frontmatter["id"] = new_id
    for list_key in (
        "depends_on",
        "traces_to",
        "target_artifacts",
        "affected_artifacts",
    ):
        raw_list = updated_frontmatter.get(list_key)
        if isinstance(raw_list, list):
            updated_frontmatter[list_key] = [
                id_mapping.get(str(item), str(item)) for item in raw_list
            ]
    new_relative = Path(relative_path).with_name(f"{new_id}.md").as_posix()
    frontmatter_yaml = yaml.safe_dump(updated_frontmatter, sort_keys=False).strip()
    body = document.body.lstrip("\n")
    suffix = f"\n{body}\n" if body else "\n"
    (worktree_path / new_relative).write_text(
        f"---\n{frontmatter_yaml}\n---{suffix}", encoding="utf-8"
    )
    return new_relative


def normalize_new_stage_artifacts(
    worktree_path: Path, existing_ids: set[str], changed_files: list[str]
) -> list[str]:
    """Renumber newly created stage artifacts that collide with existing_ids."""
    batch: list[tuple[str, ArtifactDocument | None]] = [
        (
            rel,
            parse_artifact_file(worktree_path / rel, rel)[0]
            if (worktree_path / rel).is_file()
            else None,
        )
        for rel in changed_files
    ]
    occupied = set(existing_ids) | {
        doc_id
        for doc_id, doc in load_artifacts_by_id(worktree_path).items()
        if doc.path not in set(changed_files)
    }
    id_mapping: dict[str, str] = {}
    for rel, document in batch:
        if document is None or document.artifact_type == "UNKNOWN":
            continue
        raw_id = str(document.frontmatter.get("id", Path(rel).stem))
        if raw_id in occupied or raw_id.endswith(("-NEW", "-000")):
            numbers = [
                int(item.split("-", maxsplit=1)[1])
                for item in occupied
                if item.startswith(f"{document.artifact_type}-")
                and item.split("-", maxsplit=1)[1].isdigit()
            ]
            allocated = f"{document.artifact_type}-{max(numbers, default=0) + 1:03d}"
            id_mapping[raw_id] = allocated
            occupied.add(allocated)
        else:
            id_mapping[raw_id] = raw_id
            occupied.add(raw_id)
    if all(old == new for old, new in id_mapping.items()):
        return changed_files
    for rel, document in batch:
        if document is not None and document.artifact_type != "UNKNOWN":
            (worktree_path / rel).unlink(missing_ok=True)
    return [
        _rewrite_normalized_artifact(worktree_path, rel, document, id_mapping)
        if document is not None and document.artifact_type != "UNKNOWN"
        else rel
        for rel, document in batch
    ]
