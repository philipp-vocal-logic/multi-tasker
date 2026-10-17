"""Artifact schema, section, and lifecycle validator (`mt check schemas`)."""

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

TYPE_VALIDATORS: dict[str, Any] = {
    "null": lambda value: value is None,
    "boolean": lambda value: isinstance(value, bool),
    "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
    "string": lambda value: isinstance(value, str),
    "array": lambda value: isinstance(value, list),
    "object": lambda value: isinstance(value, dict),
}


def _matches_type(value: Any, expected: str | list[str]) -> bool:
    """Check whether value matches JSON schema type string or union list."""
    if isinstance(expected, list):
        return any(_matches_type(value, item) for item in expected)
    checker = TYPE_VALIDATORS.get(expected)
    return bool(checker(value)) if checker else True


def _check_string_rules(
    value: str, schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate string pattern, enum, minLength, and maxLength constraints."""
    findings: list[Finding] = []
    pattern = schema.get("pattern")
    if isinstance(pattern, str) and not re.match(pattern, value):
        message = f"Field '{field_name}' value '{value}' does not match '{pattern}'."
        findings.append(Finding(path, 1, "TRACE_SCHEMA_PATTERN", message))
    minimum_length = schema.get("minLength")
    if isinstance(minimum_length, int) and len(value) < minimum_length:
        message = f"Field '{field_name}' length {len(value)} < minLength."
        findings.append(Finding(path, 1, "TRACE_SCHEMA_MIN_LEN", message))
    maximum_length = schema.get("maxLength")
    if isinstance(maximum_length, int) and len(value) > maximum_length:
        message = f"Field '{field_name}' length {len(value)} > maxLength."
        findings.append(Finding(path, 1, "TRACE_SCHEMA_MAX_LEN", message))
    return findings


def _check_array_rules(
    value: list[Any], schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate array minItems, maxItems, and item schemas."""
    findings: list[Finding] = []
    minimum_items = schema.get("minItems")
    if isinstance(minimum_items, int) and len(value) < minimum_items:
        message = f"Field '{field_name}' has {len(value)} items (min: {minimum_items})."
        findings.append(Finding(path, 1, "TRACE_SCHEMA_MIN_ITEMS", message))
    maximum_items = schema.get("maxItems")
    if isinstance(maximum_items, int) and len(value) > maximum_items:
        message = f"Field '{field_name}' has {len(value)} items (max: {maximum_items})."
        findings.append(Finding(path, 1, "TRACE_SCHEMA_MAX_ITEMS", message))
    item_schema = schema.get("items")
    if isinstance(item_schema, dict):
        for index, element in enumerate(value):
            findings.extend(
                validate_schema_node(
                    element, item_schema, path, f"{field_name}[{index}]"
                )
            )
    return findings


def _check_object_rules(
    value: dict[str, Any], schema: dict[str, Any], path: str, field_name: str
) -> list[Finding]:
    """Validate object required keys, additionalProperties, and property schemas."""
    prefix = f"{field_name}." if field_name else ""
    properties = schema.get("properties", {})
    findings: list[Finding] = []
    if schema.get("additionalProperties") is False and isinstance(properties, dict):
        findings.extend(
            Finding(
                path, 1, "TRACE_SCHEMA_UNKNOWN_FIELD", f"Unknown field '{prefix}{key}'."
            )
            for key in value
            if key not in properties
        )
    for required_key in schema.get("required", []):
        if required_key not in value:
            message = f"Missing required frontmatter field '{prefix}{required_key}'."
            findings.append(Finding(path, 1, "TRACE_SCHEMA_REQUIRED", message))
    if isinstance(properties, dict):
        for key, sub_schema in properties.items():
            if key in value and isinstance(sub_schema, dict):
                findings.extend(
                    validate_schema_node(value[key], sub_schema, path, f"{prefix}{key}")
                )
    return findings


def validate_schema_node(
    value: Any, schema: dict[str, Any], path: str, field_name: str = ""
) -> list[Finding]:
    """Validate a parsed YAML value against a JSON-Schema node."""
    expected_type = schema.get("type")
    label = field_name or "<root>"
    if expected_type is not None and not _matches_type(value, expected_type):
        message = f"Field '{label}' has invalid type (expected {expected_type})."
        return [Finding(path, 1, "TRACE_SCHEMA_TYPE", message)]
    enum_values = schema.get("enum")
    if isinstance(enum_values, list) and value not in enum_values:
        message = f"Field '{label}' value '{value}' not in {enum_values}."
        return [Finding(path, 1, "TRACE_SCHEMA_ENUM", message)]
    if isinstance(value, int) and not isinstance(value, bool):
        minimum = schema.get("minimum")
        if isinstance(minimum, int) and value < minimum:
            message = f"Field '{label}' value {value} < minimum {minimum}."
            return [Finding(path, 1, "TRACE_SCHEMA_MIN", message)]
    if isinstance(value, str):
        return _check_string_rules(value, schema, path, label)
    if isinstance(value, list):
        return _check_array_rules(value, schema, path, label)
    if isinstance(value, dict):
        return _check_object_rules(value, schema, path, field_name)
    return []


def _check_artifact_sections(
    document: ArtifactDocument, artifact_configuration: dict[str, Any]
) -> list[Finding]:
    """Check required sections and word/line/paragraph limits on an ArtifactDocument."""
    findings = [
        Finding(
            document.path,
            document.body_start_line,
            "LIMIT_SECTION_MISSING",
            f"Missing required section '## {required_section}'.",
        )
        for required_section in artifact_configuration.get("required_sections", [])
        if required_section not in document.sections
    ]
    for section_name, rule in artifact_configuration.get("sections", {}).items():
        if section_name not in document.sections:
            continue
        section = document.sections[section_name]
        words = len(section.content.split())
        lines = len(section.content.splitlines()) if section.content else 0
        max_words, max_lines = rule.get("max_words"), rule.get("max_lines")
        line_number = section.start_line
        if isinstance(max_words, int) and words > max_words:
            message = f"Section '{section_name}' has {words} words (max: {max_words})."
            findings.append(
                Finding(document.path, line_number, "LIMIT_SECTION_WORDS", message)
            )
        if isinstance(max_lines, int) and lines > max_lines:
            message = f"Section '{section_name}' has {lines} lines (max: {max_lines})."
            findings.append(
                Finding(document.path, line_number, "LIMIT_SECTION_LINES", message)
            )
        if rule.get("single_paragraph_only") and "\n\n" in section.content.strip():
            message = f"Section '{section_name}' must be a single paragraph."
            findings.append(
                Finding(document.path, line_number, "LIMIT_SINGLE_PARAGRAPH", message)
            )
    return findings


def _check_criterion_and_review_words(
    document: ArtifactDocument, artifact_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce max_criterion_words on REQ ACs and max_finding_words on REV findings."""
    findings: list[Finding] = []
    max_criterion_words = artifact_configuration.get("max_criterion_words")
    if isinstance(max_criterion_words, int):
        keys = ("given", "when", "then", "criterion")
        for criterion in document.frontmatter.get("acceptance_criteria", []):
            if isinstance(criterion, dict):
                text = " ".join(
                    str(criterion.get(key, "")) for key in keys if key in criterion
                )
                words = len(text.split())
                if words > max_criterion_words:
                    message = (
                        f"Criterion has {words} words (max: {max_criterion_words})."
                    )
                    findings.append(
                        Finding(document.path, 1, "LIMIT_CRITERION_WORDS", message)
                    )
    max_finding_words = artifact_configuration.get("max_finding_words")
    if isinstance(max_finding_words, int):
        for item in document.frontmatter.get("findings", []):
            words = len(str(item).split())
            if words > max_finding_words:
                message = (
                    f"Review finding has {words} words (max: {max_finding_words})."
                )
                findings.append(
                    Finding(document.path, 1, "LIMIT_FINDING_WORDS", message)
                )
    return findings


def _check_artifact_frontmatter_limits(
    document: ArtifactDocument, artifact_configuration: dict[str, Any]
) -> list[Finding]:
    """Check frontmatter collection size limits and item word limits."""
    findings = _check_criterion_and_review_words(document, artifact_configuration)
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
