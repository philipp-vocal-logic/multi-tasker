"""Artifact frontmatter schema and section structure checker (`mt check schemas`)."""

from fnmatch import fnmatch
from pathlib import Path
import re
from typing import Any

from src.checkers.common import collect_repository_files
from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import (
    load_yaml_file,
    parse_artifact_file,
    validate_pipeline_policy,
)


def _matches_json_type(value: Any, expected_type: str) -> bool:
    """Verify Python value matches a JSON Schema primitive or container type."""
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "array":
        return isinstance(value, list)
    if expected_type == "object":
        return isinstance(value, dict)
    return True


def _validate_string_constraints(
    value: str, schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate string enum, pattern, and minLength constraints."""
    findings: list[Finding] = []
    allowed_enum = schema.get("enum")
    if isinstance(allowed_enum, list) and value not in allowed_enum:
        message = f"Field '{field_name}' value '{value}' not in {allowed_enum}."
        findings.append(Finding(path, 1, "SCHEMA_ENUM_MISMATCH", message))
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and not re.match(pattern, value):
        message = f"Field '{field_name}' value '{value}' fails pattern '{pattern}'."
        findings.append(Finding(path, 1, "SCHEMA_PATTERN_MISMATCH", message))
    min_length = schema.get("minLength")
    if isinstance(min_length, int) and len(value) < min_length:
        message = f"Field '{field_name}' is shorter than minLength {min_length}."
        findings.append(Finding(path, 1, "SCHEMA_MIN_LENGTH", message))
    return findings


def _validate_array_constraints(
    value: list[Any], schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate array minItems and item schemas."""
    findings: list[Finding] = []
    min_items = schema.get("minItems")
    if isinstance(min_items, int) and len(value) < min_items:
        message = (
            f"Field '{field_name}' has {len(value)} items (minItems: {min_items})."
        )
        findings.append(Finding(path, 1, "SCHEMA_MIN_ITEMS", message))
    item_schema = schema.get("items")
    if isinstance(item_schema, dict):
        for index, item in enumerate(value):
            findings.extend(
                validate_schema_node(item, item_schema, path, f"{field_name}[{index}]")
            )
    return findings


def _validate_object_constraints(
    value: dict[str, Any], schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate required keys, additionalProperties, and nested properties."""
    findings: list[Finding] = []
    required_keys: list[str] = schema.get("required", [])
    for key in required_keys:
        if key not in value:
            label = f"{field_name}.{key}" if field_name != "root" else key
            message = f"Missing required frontmatter field '{label}'."
            findings.append(Finding(path, 1, "SCHEMA_REQUIRED_MISSING", message))
    properties: dict[str, Any] = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for key in value:
            if key not in properties:
                message = f"Unknown frontmatter field '{key}' is not allowed."
                findings.append(Finding(path, 1, "SCHEMA_ADDITIONAL_PROP", message))
    for key, subschema in properties.items():
        if key in value and isinstance(subschema, dict):
            label = f"{field_name}.{key}" if field_name != "root" else key
            findings.extend(validate_schema_node(value[key], subschema, path, label))
    return findings


def validate_schema_node(
    value: Any,
    schema: dict[str, Any],
    path: str,
    field_name: str = "root",
) -> list[Finding]:
    """Recursively validate a parsed YAML node against a JSON Schema subset."""
    expected_type = schema.get("type")
    if isinstance(expected_type, str) and not _matches_json_type(value, expected_type):
        message = f"Field '{field_name}' must be of type '{expected_type}'."
        return [Finding(path, 1, "SCHEMA_TYPE_MISMATCH", message)]
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            message = f"Field '{field_name}' value {value} is below minimum {minimum}."
            return [Finding(path, 1, "SCHEMA_MINIMUM", message)]
    if isinstance(value, str):
        return _validate_string_constraints(value, schema, path, field_name)
    if isinstance(value, list):
        return _validate_array_constraints(value, schema, path, field_name)
    if isinstance(value, dict):
        return _validate_object_constraints(value, schema, path, field_name)
    return []


def _check_single_section_limits(
    document: ArtifactDocument,
    section_name: str,
    section_limits: dict[str, Any],
) -> list[Finding]:
    """Check max_words, max_lines, and single_paragraph_only on one section."""
    if section_name not in document.sections:
        return []
    section = document.sections[section_name]
    findings: list[Finding] = []
    max_words = section_limits.get("max_words")
    word_count = len(section.content.split())
    if isinstance(max_words, int) and word_count > max_words:
        message = f"Section '{section_name}' has {word_count} words (max: {max_words})."
        findings.append(
            Finding(document.path, section.start_line, "LIMIT_SECTION_WORDS", message)
        )
    max_lines = section_limits.get("max_lines")
    non_empty_lines = [line for line in section.content.splitlines() if line.strip()]
    if isinstance(max_lines, int) and len(non_empty_lines) > max_lines:
        message = (
            f"Section '{section_name}' has {len(non_empty_lines)} lines "
            f"(max: {max_lines})."
        )
        findings.append(
            Finding(document.path, section.start_line, "LIMIT_SECTION_LINES", message)
        )
    if (
        section_limits.get("single_paragraph_only")
        and "\n\n" in section.content.strip()
    ):
        message = f"Section '{section_name}' must be a single paragraph."
        findings.append(
            Finding(
                document.path, section.start_line, "SCHEMA_SINGLE_PARAGRAPH", message
            )
        )
    return findings


def _check_artifact_sections(
    document: ArtifactDocument, artifact_configuration: dict[str, Any]
) -> list[Finding]:
    """Validate required sections and per-section limits for an artifact."""
    findings: list[Finding] = []
    for required_section in artifact_configuration.get("required_sections", []):
        if required_section not in document.sections:
            message = f"Missing required section '## {required_section}'."
            findings.append(
                Finding(
                    document.path,
                    document.body_start_line,
                    "SCHEMA_MISSING_SECTION",
                    message,
                )
            )
    section_rules: dict[str, Any] = artifact_configuration.get("sections", {})
    for section_name, section_limits in section_rules.items():
        if isinstance(section_limits, dict):
            findings.extend(
                _check_single_section_limits(document, section_name, section_limits)
            )
    return findings


def _check_criterion_word_limits(
    document: ArtifactDocument, max_criterion_words: Any
) -> list[Finding]:
    """Check max_criterion_words on REQ acceptance_criteria entries."""
    if not isinstance(max_criterion_words, int):
        return []
    findings: list[Finding] = []
    for criterion in document.frontmatter.get("acceptance_criteria", []):
        if not isinstance(criterion, dict):
            continue
        combined = " ".join(
            str(criterion.get(part, "")) for part in ("given", "when", "then")
        )
        words = len(combined.split())
        if words > max_criterion_words:
            criterion_id = criterion.get("id", "AC")
            message = (
                f"Criterion '{criterion_id}' has {words} words "
                f"(max: {max_criterion_words})."
            )
            findings.append(Finding(document.path, 1, "LIMIT_CRITERION_WORDS", message))
    return findings


def _check_finding_word_limits(
    document: ArtifactDocument, max_finding_words: Any
) -> list[Finding]:
    """Check max_finding_words on REV findings entries."""
    if not isinstance(max_finding_words, int):
        return []
    findings: list[Finding] = []
    for entry in document.frontmatter.get("findings", []):
        words = len(str(entry).split())
        if words > max_finding_words:
            message = f"Review finding has {words} words (max: {max_finding_words})."
            findings.append(Finding(document.path, 1, "LIMIT_FINDING_WORDS", message))
    return findings


def _check_artifact_frontmatter_limits(
    document: ArtifactDocument, artifact_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce body word counts and frontmatter array/item limits."""
    findings = [
        *_check_criterion_word_limits(
            document, artifact_configuration.get("max_criterion_words")
        ),
        *_check_finding_word_limits(
            document, artifact_configuration.get("max_finding_words")
        ),
    ]
    max_body_words = artifact_configuration.get("max_body_words")
    body_words = len(document.body.split())
    if isinstance(max_body_words, int) and body_words > max_body_words:
        message = f"Body has {body_words} words (max: {max_body_words})."
        findings.append(
            Finding(
                document.path, document.body_start_line, "LIMIT_BODY_WORDS", message
            )
        )
    list_checks = [
        ("max_acceptance_criteria", "acceptance_criteria", "LIMIT_MAX_AC"),
        ("max_write_files", "write_files", "LIMIT_MAX_WRITE_FILES"),
        ("max_required_files", "required_files", "LIMIT_MAX_REQUIRED_FILES"),
        ("max_findings_per_record", "findings", "LIMIT_MAX_FINDINGS"),
    ]
    for configuration_key, frontmatter_key, rule_id in list_checks:
        limit = artifact_configuration.get(configuration_key)
        items = document.frontmatter.get(frontmatter_key, [])
        if isinstance(limit, int) and isinstance(items, list) and len(items) > limit:
            message = (
                f"Field '{frontmatter_key}' has {len(items)} items (max: {limit})."
            )
            findings.append(Finding(document.path, 1, rule_id, message))
    return findings


def _check_single_document(
    document: ArtifactDocument,
    schemas: dict[str, Any],
    artifact_configurations: dict[str, Any],
) -> list[Finding]:
    """Validate path_glob, json_schema, and section/frontmatter limits."""
    findings: list[Finding] = []
    type_configuration = schemas.get(document.artifact_type, {})
    path_glob = type_configuration.get("path_glob")
    if document.artifact_type == "UNKNOWN" or (
        isinstance(path_glob, str) and not fnmatch(document.path, path_glob)
    ):
        message = f"File '{document.path}' does not match any schema path_glob."
        findings.append(Finding(document.path, 1, "TRACE_PATH_GLOB_MISMATCH", message))
    json_schema = type_configuration.get("json_schema")
    if isinstance(json_schema, dict):
        findings.extend(
            validate_schema_node(document.frontmatter, json_schema, document.path)
        )
    if document.artifact_type in artifact_configurations:
        configuration = artifact_configurations[document.artifact_type]
        findings.extend(_check_artifact_sections(document, configuration))
        findings.extend(_check_artifact_frontmatter_limits(document, configuration))
    return findings


def check_schemas(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/schemas.yaml and policy/pipeline.yaml across artifacts."""
    schema_path = repository_root / "policy" / "schemas.yaml"
    if not schema_path.exists():
        message = "Missing policy/schemas.yaml."
        return [Finding("policy/schemas.yaml", 1, "SCHEMA_POLICY_MISSING", message)]
    policy = load_yaml_file(schema_path)
    schemas: dict[str, Any] = policy.get("schemas", {})
    artifact_configurations: dict[str, Any] = policy.get("artifacts", {})
    for artifact_type, mapping in policy.get("state_transitions", {}).items():
        if artifact_type and isinstance(mapping, dict):
            _ = list(mapping.items())
    findings = validate_pipeline_policy(repository_root)
    for markdown_path in collect_repository_files(
        repository_root,
        target_paths,
        ("artifacts",),
        {".md"},
        require_folder_prefix=True,
    ):
        relative_path = markdown_path.relative_to(repository_root).as_posix()
        document, errors = parse_artifact_file(markdown_path, relative_path)
        findings.extend(errors)
        if document is not None:
            findings.extend(
                _check_single_document(document, schemas, artifact_configurations)
            )
    return sorted(set(findings))
