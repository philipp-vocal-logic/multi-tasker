"""Deterministic role prompt synthesizer from policies and repository artifacts."""

import os
from pathlib import Path
from typing import Any

import yaml

from src.checkers.limits_checker import collect_refactoring_targets
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
VALID_CONTEXT_MODES = {"inline", "paths"}


def resolve_context_mode(
    repository_root: Path,
    document: ArtifactDocument | None = None,
    context_mode_override: str | None = None,
) -> str:
    """Resolve context_mode ('inline' or 'paths') with CLI > Task > Policy order."""
    cli_mode = context_mode_override or os.environ.get("MT_CONTEXT_MODE")
    if cli_mode:
        return cli_mode.strip()
    if document is not None:
        task_mode = str(document.frontmatter.get("context_mode", "")).strip()
        if task_mode:
            return task_mode
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    execution_config: dict[str, Any] = permissions.get("execution_environments", {})
    return (
        str(execution_config.get("default_context_mode", "inline")).strip() or "inline"
    )


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
    context_mode: str,
) -> list[str]:
    """Render WriteScope, state transitions, and escalation rules for agent_role."""
    lines = [
        f"# Role Prompt: `{agent_role}`",
        "",
        "## 1. WriteScope & Permission Contract",
        f"- **Context Mode**: `{context_mode}`",
        f"- **Global Forbidden Writes**: `{', '.join(global_forbidden) or 'none'}`",
    ]
    for rule in role_configuration.get("allowed_write", []):
        existing = ", ".join(
            str(state) for state in rule.get("allowed_existing_states", [])
        )
        targets = ", ".join(
            str(state) for state in rule.get("allowed_target_states", [])
        )
        lines.append(
            f"- **Allowed Write**: `{rule.get('path', '')}` "
            f"(existing: `{existing or 'task-scoped'}` -> target: `{targets or 'any'}`)"
        )
    escalation_rules = role_configuration.get("escalation_write", [])
    if escalation_rules:
        paths = ", ".join(f"`{rule.get('path', '')}`" for rule in escalation_rules)
        routes = ", ".join(
            f"`{cat}` -> `{target[0]}`" for cat, target in CATEGORY_ROUTES.items()
        )
        lines.append(f"- **Escalation Write**: {paths} ({routes})")
    return [*lines, ""]


def _render_artifact_schema_block(
    artifact_type: str, schemas_policy: dict[str, Any], context_mode: str = "inline"
) -> list[str]:
    """Render frontmatter schema and required Markdown section constraints."""
    artifact_rules = schemas_policy.get("artifacts", {}).get(artifact_type, {})
    schema_def = schemas_policy.get("schemas", {}).get(artifact_type, {})
    if not artifact_rules and not schema_def:
        return []
    lines = [f"### `{artifact_type}` Output Contract"]
    if context_mode == "inline" and schema_def:
        dumped = yaml.safe_dump(schema_def, sort_keys=False).strip()
        lines.extend(["```yaml", dumped, "```"])
    elif schema_def:
        lines.append(
            f"- **Schema Reference**: `policy/schemas.yaml` (`schemas.{artifact_type}`)"
        )
    for name, lim in artifact_rules.get("sections", {}).items():
        words = lim.get("max_words", "unlimited")
        max_ln = lim.get("max_lines", "unlimited")
        lines.append(
            f"- Section `## {name}`: max `{words}` words, max `{max_ln}` lines"
        )
    return [*lines, ""]


def _render_glossary_constraints(repository_root: Path, context_mode: str) -> list[str]:
    """Render canonical glossary terms and inline forbidden_synonyms when enabled."""
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if not glossary_path.exists():
        return []
    terms: list[dict[str, Any]] = load_yaml_file(glossary_path).get("terms", [])
    canonical_names = [str(item.get("canonical", "")) for item in terms]
    lines = [f"- **Canonical Terms**: {', '.join(canonical_names)}"]
    if context_mode == "inline":
        forbidden_pairs = [
            f"`{item.get('canonical')}` != "
            f"{', '.join(item.get('forbidden_synonyms', [])[:3])}"
            for item in terms
            if item.get("forbidden_synonyms")
        ]
        lines.append(f"- **Forbidden Synonyms**: {'; '.join(forbidden_pairs)}")
    return lines


def _render_code_and_glossary_section(
    repository_root: Path, agent_role: str, context_mode: str = "inline"
) -> list[str]:
    """Render sizing limits, clean code rules, and canonical glossary terms."""
    lines = ["## 3. Vocabulary & Engineering Constraints"]
    if context_mode == "paths":
        lines.append(
            "- **Policy Files**: `policy/limits.yaml`, `policy/clean_code.yaml`, "
            "`policy/glossary.yaml`"
        )
    elif agent_role in {"worker-agent", "review-agent"}:
        limits_path = repository_root / "policy" / "limits.yaml"
        if limits_path.exists():
            source_limits = load_yaml_file(limits_path).get("source_code", {})
            pairs = ", ".join(f"`{key}={val}`" for key, val in source_limits.items())
            lines.append(f"- **Source Limits**: {pairs}")
        clean_path = repository_root / "policy" / "clean_code.yaml"
        if clean_path.exists():
            ast_rules = load_yaml_file(clean_path).get("ast_rules", {})
            pairs = ", ".join(f"`{key}={val}`" for key, val in ast_rules.items())
            lines.append(f"- **Clean Code AST Rules**: {pairs}")
    if agent_role in {"specification-agent", "planner-agent"}:
        hints = collect_refactoring_targets(repository_root)
        if hints:
            items = ", ".join(f"`{item.path}` ({item.line} lines)" for item in hints)
            lines.append(f"- **Refactoring Targets (Warning)**: {items}")
    return [*lines, *_render_glossary_constraints(repository_root, context_mode), ""]


def _collect_context_documents(
    target_document: ArtifactDocument, by_identifier: dict[str, ArtifactDocument]
) -> list[ArtifactDocument]:
    """Return target_document followed by its upstream traces_to and decisions."""
    upstream_ids = [
        *target_document.frontmatter.get("traces_to", []),
        *target_document.frontmatter.get("decisions", []),
    ]
    upstream = [
        by_identifier[str(item)] for item in upstream_ids if str(item) in by_identifier
    ]
    return [target_document, *upstream]


def _render_code_file_block(
    repository_root: Path, heading_prefix: str, relative_path: str, context_mode: str
) -> list[str]:
    """Render a Required File or Write File entry as inline content or path."""
    lines = [f"### {heading_prefix} `{relative_path}`", f"Path: `{relative_path}`"]
    file_path = repository_root / relative_path
    if context_mode == "inline" and file_path.is_file():
        lines.extend(["```python", file_path.read_text("utf-8").strip(), "```"])
    return [*lines, ""]


def _render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
    context_mode: str = "inline",
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write file contents."""
    lines = ["## 4. Scoped Target & Upstream Context", ""]
    for document in _collect_context_documents(target_document, by_identifier):
        artifact_id = str(document.frontmatter.get("id", document.path))
        lines.append(f"### Artifact `{artifact_id}` (`{document.path}`)")
        lines.append(f"Path: `{document.path}`")
        if context_mode == "inline":
            raw = (repository_root / document.path).read_text("utf-8").strip()
            lines.extend(["```markdown", raw, "```"])
        lines.append("")
    for path in target_document.frontmatter.get("required_files", []):
        if (repository_root / str(path)).is_file():
            lines.extend(
                _render_code_file_block(
                    repository_root, "Required File", str(path), context_mode
                )
            )
    for path in target_document.frontmatter.get("write_files", []):
        lines.extend(
            _render_code_file_block(
                repository_root, "Write File", str(path), context_mode
            )
        )
    return lines


def _assemble_prompt_sections(
    repository_root: Path,
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
    context_mode: str,
) -> list[str]:
    """Assemble permissions, mission, schemas, and vocabulary sections."""
    schemas_path = repository_root / "policy" / "schemas.yaml"
    schemas_policy = load_yaml_file(schemas_path) if schemas_path.exists() else {}
    primary_type = ROLE_TO_OUTPUT_SCHEMA.get(agent_role, "REQ")
    lines = [
        *_render_permissions_section(
            agent_role, role_configuration, global_forbidden, context_mode
        ),
        f"**Mission**: {_find_role_definition(repository_root, agent_role)}",
        "",
        "## 2. Output Schemas & Section Budgets",
        *_render_artifact_schema_block(primary_type, schemas_policy, context_mode),
    ]
    if role_configuration.get("escalation_write"):
        lines.extend(_render_artifact_schema_block("ESC", schemas_policy, context_mode))
    lines.extend(
        _render_code_and_glossary_section(repository_root, agent_role, context_mode)
    )
    return lines


def _resolve_prompt_target(
    repository_root: Path, target_id: str | None, context_mode: str | None
) -> tuple[dict[str, ArtifactDocument], ArtifactDocument | None, str, list[Finding]]:
    """Load artifacts, resolve target_id and context_mode, and return Findings."""
    by_identifier = load_artifacts_by_id(repository_root)
    target_document = by_identifier.get(target_id) if target_id else None
    if target_id is not None and target_document is None:
        message = f"Target artifact '{target_id}' not found."
        return (
            by_identifier,
            None,
            "",
            [Finding(target_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)],
        )
    resolved_mode = resolve_context_mode(repository_root, target_document, context_mode)
    if resolved_mode not in VALID_CONTEXT_MODES:
        message = f"Invalid context_mode '{resolved_mode}'."
        finding = Finding(
            "policy/permissions.yaml", 1, "CLI_INVALID_CONTEXT_MODE", message
        )
        return by_identifier, None, "", [finding]
    return by_identifier, target_document, resolved_mode, []


def build_agent_prompt(
    repository_root: Path,
    agent_role: str,
    target_id: str | None = None,
    context_mode: str | None = None,
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
    by_id, target_doc, mode, findings = _resolve_prompt_target(
        repository_root, target_id, context_mode
    )
    if findings:
        return "", findings
    forbidden = [str(item) for item in permissions.get("global_forbidden_write", [])]
    lines = _assemble_prompt_sections(
        repository_root, agent_role, agents[agent_role], forbidden, mode
    )
    if target_doc is not None:
        lines.extend(
            _render_target_context_section(repository_root, target_doc, by_id, mode)
        )
    return "\n".join(lines).strip() + "\n", []


def resolve_task_execution(
    repository_root: Path,
    document: ArtifactDocument,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
    agent_role: str = "worker-agent",
) -> tuple[str | None, str, str]:
    """Resolve (command_template, environment_name, model_name) for an agent run."""
    agent_command, model_override, environment_override = options
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    execution_config: dict[str, Any] = permissions.get("execution_environments", {})
    role_config: dict[str, Any] = permissions.get("agents", {}).get(agent_role, {})
    default_env = str(execution_config.get("default_environment", "agy"))
    default_model = str(execution_config.get("default_model", "gemini-3.8-flash-high"))
    role_model = str(role_config.get("model", "")).strip()
    environments: dict[str, Any] = execution_config.get("environments", {})
    task_env = str(document.frontmatter.get("execution_environment", "")).strip()
    task_model = str(document.frontmatter.get("model", "")).strip()
    environment_name = environment_override or task_env or default_env
    model_name = model_override or task_model or role_model or default_model
    if agent_command:
        return agent_command, environment_name, model_name
    if environment_override or task_env:
        template = environments.get(environment_name)
        return (str(template) if template else None), environment_name, model_name
    return None, environment_name, model_name


def prepare_worker_invocation(
    worktree_path: Path,
    document: ArtifactDocument,
    prompt_file: Path,
    execution_context: tuple[str, str, str],
    context_mode_override: str | None = None,
) -> tuple[str, dict[str, str]]:
    """Write .mt_prompt.md and build command and environment for worker execution."""
    task_id = str(document.frontmatter["id"])
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    mode = resolve_context_mode(worktree_path, document, context_mode_override)
    prompt_text, _ = build_agent_prompt(worktree_path, "worker-agent", task_id, mode)
    prompt_file.write_text(prompt_text, encoding="utf-8")
    command_template, environment_name, model_name = execution_context
    rendered_command = (
        command_template.replace("{model}", model_name)
        .replace("{task_id}", task_id)
        .replace("{prompt_file}", str(prompt_file))
        .replace("{context_mode}", mode)
    )
    environment = {
        **os.environ,
        "PYTHONPATH": f"{worktree_path}{os.pathsep}{Path(__file__).parents[2]}",
        "MT_AGENT_ROLE": "worker-agent",
        "MT_TASK_ID": task_id,
        "MT_WRITE_FILES": ",".join(write_files),
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
        "MT_CONTEXT_MODE": mode,
    }
    return rendered_command, environment
