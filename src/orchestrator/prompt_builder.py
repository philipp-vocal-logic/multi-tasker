"""Deterministic role prompt synthesizer from policies and repository artifacts."""

from pathlib import Path
from typing import Any

import yaml

from src.domain.models import ArtifactDocument, Finding
from src.domain.parser import load_artifacts_by_id, load_yaml_file
from src.orchestrator.router import CATEGORY_ROUTES

ROLE_TO_OUTPUT_SCHEMA: dict[str, str] = {
    "requirement-agent": "REQ",
    "specification-agent": "SPEC",
    "planner-agent": "TASK",
    "worker-agent": "TASK",
    "review-agent": "REV",
}


def _find_role_definition(repository_root: Path, agent_role: str) -> str:
    """Extract canonical role definition from policy/glossary.yaml."""
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if not glossary_path.exists():
        return f"Scoped agent role `{agent_role}`."
    terms: list[dict[str, Any]] = load_yaml_file(glossary_path).get("terms", [])
    for entry in terms:
        allowed_forms = [str(item) for item in entry.get("allowed_forms", [])]
        if agent_role in allowed_forms:
            return " ".join(str(entry.get("definition", "")).split())
    return f"Scoped agent role `{agent_role}`."


def _render_permissions_section(
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
) -> list[str]:
    """Render WriteScope, state transitions, and escalation rules for agent_role."""
    lines = [
        f"# Role Prompt: `{agent_role}`",
        "",
        "## 1. WriteScope & Permission Contract",
        f"- **Global Forbidden Writes**: `{', '.join(global_forbidden) or 'none'}`",
    ]
    for rule in role_configuration.get("allowed_write", []):
        path_pattern = str(rule.get("path", ""))
        existing = ", ".join(
            str(state) for state in rule.get("allowed_existing_states", [])
        )
        targets = ", ".join(
            str(state) for state in rule.get("allowed_target_states", [])
        )
        lines.append(
            f"- **Allowed Write**: `{path_pattern}` "
            f"(existing: `{existing or 'task-scoped'}` -> target: `{targets or 'any'}`)"
        )
    escalation_rules = role_configuration.get("escalation_write", [])
    if escalation_rules:
        escalation_paths = ", ".join(
            f"`{rule.get('path', '')}`" for rule in escalation_rules
        )
        routes = ", ".join(
            f"`{cat}` -> `{target[0]}`" for cat, target in CATEGORY_ROUTES.items()
        )
        lines.append(f"- **Escalation Write**: {escalation_paths} ({routes})")
    lines.append("")
    return lines


def _render_artifact_schema_block(
    artifact_type: str, schemas_policy: dict[str, Any]
) -> list[str]:
    """Render frontmatter schema and required Markdown section constraints."""
    artifact_rules = schemas_policy.get("artifacts", {}).get(artifact_type, {})
    schema_definition = schemas_policy.get("schemas", {}).get(artifact_type, {})
    if not artifact_rules and not schema_definition:
        return []
    lines = [f"### `{artifact_type}` Output Contract"]
    if schema_definition:
        serialized = yaml.safe_dump(schema_definition, sort_keys=False).strip()
        lines.extend(["```yaml", serialized, "```"])
    sections: dict[str, Any] = artifact_rules.get("sections", {})
    for section_name, limits in sections.items():
        max_words = limits.get("max_words", "unlimited")
        max_lines = limits.get("max_lines", "unlimited")
        lines.append(
            f"- Section `## {section_name}`: max `{max_words}` words, "
            f"max `{max_lines}` lines"
        )
    lines.append("")
    return lines


def _render_code_and_glossary_section(
    repository_root: Path, agent_role: str
) -> list[str]:
    """Render sizing limits, clean code rules, and canonical glossary terms."""
    lines = ["## 3. Vocabulary & Engineering Constraints"]
    if agent_role in {"worker-agent", "review-agent"}:
        limits_path = repository_root / "policy" / "limits.yaml"
        if limits_path.exists():
            source_limits = load_yaml_file(limits_path).get("source_code", {})
            formatted = ", ".join(
                f"`{key}={value}`" for key, value in source_limits.items()
            )
            lines.append(f"- **Source Limits**: {formatted}")
        clean_path = repository_root / "policy" / "clean_code.yaml"
        if clean_path.exists():
            ast_rules = load_yaml_file(clean_path).get("ast_rules", {})
            formatted_ast = ", ".join(
                f"`{key}={value}`" for key, value in ast_rules.items()
            )
            lines.append(f"- **Clean Code AST Rules**: {formatted_ast}")
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if glossary_path.exists():
        terms = load_yaml_file(glossary_path).get("terms", [])
        canonical_names = [str(item.get("canonical", "")) for item in terms]
        lines.append(f"- **Canonical Terms**: {', '.join(canonical_names)}")
    lines.append("")
    return lines


def _collect_context_documents(
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[ArtifactDocument]:
    """Return target_document followed by its upstream traces_to and decisions."""
    documents = [target_document]
    upstream_ids = [
        *(str(item) for item in target_document.frontmatter.get("traces_to", [])),
        *(str(item) for item in target_document.frontmatter.get("decisions", [])),
    ]
    for upstream_id in upstream_ids:
        if upstream_id in by_identifier:
            documents.append(by_identifier[upstream_id])
    return documents


def _render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required file contents."""
    lines = ["## 4. Scoped Target & Upstream Context", ""]
    for document in _collect_context_documents(target_document, by_identifier):
        artifact_id = str(document.frontmatter.get("id", document.path))
        raw_text = (repository_root / document.path).read_text(encoding="utf-8").strip()
        lines.extend(
            [
                f"### Artifact `{artifact_id}` (`{document.path}`)",
                "```markdown",
                raw_text,
                "```",
                "",
            ]
        )
    for relative_path in target_document.frontmatter.get("required_files", []):
        file_path = repository_root / str(relative_path)
        if file_path.is_file():
            lines.extend(
                [f"### Required File `{relative_path}`", f"Path: `{relative_path}`", ""]
            )
    return lines


def _assemble_prompt_sections(
    repository_root: Path,
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
) -> list[str]:
    """Assemble permissions, mission, schemas, and vocabulary sections."""
    schemas_path = repository_root / "policy" / "schemas.yaml"
    schemas_policy = load_yaml_file(schemas_path) if schemas_path.exists() else {}
    primary_type = ROLE_TO_OUTPUT_SCHEMA.get(agent_role, "REQ")
    lines = [
        *_render_permissions_section(agent_role, role_configuration, global_forbidden),
        f"**Mission**: {_find_role_definition(repository_root, agent_role)}",
        "",
        "## 2. Output Schemas & Section Budgets",
        *_render_artifact_schema_block(primary_type, schemas_policy),
    ]
    if role_configuration.get("escalation_write"):
        lines.extend(_render_artifact_schema_block("ESC", schemas_policy))
    lines.extend(_render_code_and_glossary_section(repository_root, agent_role))
    return lines


def build_agent_prompt(
    repository_root: Path, agent_role: str, target_id: str | None = None
) -> tuple[str, list[Finding]]:
    """Synthesize a deterministic role prompt from policy/*.yaml and target_id."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    agents: dict[str, Any] = permissions.get("agents", {})
    if agent_role not in agents:
        message = f"Unknown agent role '{agent_role}'."
        return "", [
            Finding("policy/permissions.yaml", 1, "CLI_UNKNOWN_AGENT_ROLE", message)
        ]
    by_identifier = load_artifacts_by_id(repository_root)
    target_document = by_identifier.get(target_id) if target_id else None
    if target_id is not None and target_document is None:
        message = f"Target artifact '{target_id}' not found."
        return "", [Finding(target_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    role_configuration: dict[str, Any] = agents[agent_role]
    global_forbidden = [
        str(item) for item in permissions.get("global_forbidden_write", [])
    ]
    lines = _assemble_prompt_sections(
        repository_root, agent_role, role_configuration, global_forbidden
    )
    if target_document is not None:
        lines.extend(
            _render_target_context_section(
                repository_root, target_document, by_identifier
            )
        )
    return "\n".join(lines).strip() + "\n", []


def resolve_task_execution(
    repository_root: Path,
    document: ArtifactDocument,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
) -> tuple[str | None, str, str]:
    """Resolve (command_template, environment_name, model_name) for a Task."""
    agent_command, model_override, environment_override = options
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    execution_config: dict[str, Any] = permissions.get("execution_environments", {})
    default_env = str(execution_config.get("default_environment", "agy"))
    default_model = str(execution_config.get("default_model", "gemini-3.8-flash-high"))
    environments: dict[str, Any] = execution_config.get("environments", {})
    task_env = str(document.frontmatter.get("execution_environment", "")).strip()
    task_model = str(document.frontmatter.get("model", "")).strip()
    environment_name = environment_override or task_env or default_env
    model_name = model_override or task_model or default_model
    if agent_command:
        return agent_command, environment_name, model_name
    if environment_override or task_env:
        template = environments.get(environment_name)
        return (str(template) if template else None), environment_name, model_name
    return None, environment_name, model_name
