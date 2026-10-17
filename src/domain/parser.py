"""YAML and Markdown frontmatter parser and artifact repository utilities."""

from pathlib import Path
from typing import Any

import yaml

from src.domain.models import ArtifactDocument, Finding, SectionSlice

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
    max_steps = bounds.get("max_steps_per_run", 0)
    max_reroutes = bounds.get("max_auto_reroutes", -1)
    if (
        not isinstance(max_steps, int)
        or max_steps < 1
        or not isinstance(max_reroutes, int)
        or max_reroutes < 0
    ):
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
