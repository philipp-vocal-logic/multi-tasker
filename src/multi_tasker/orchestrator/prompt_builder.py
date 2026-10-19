"""Deterministic self-contained role prompt synthesizer from policies and artifacts."""

import os
from pathlib import Path
from typing import Any

import yaml

from multi_tasker.checkers.limits_checker import collect_refactoring_targets
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import (
    load_artifacts_by_id,
    load_yaml_file,
    next_artifact_id,
)
from multi_tasker.orchestrator.router import CATEGORY_ROUTES

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


def _render_section_budgets(artifact_rules: dict[str, Any]) -> list[str]:
    """Render top-level artifact limits and per-section word and line budgets."""
    lines = [
        f"- **Artifact Limit `{key}`**: `{val}`"
        for key, val in artifact_rules.items()
        if key not in {"required_sections", "sections"}
    ]
    for name, lim in artifact_rules.get("sections", {}).items():
        words = lim.get("max_words", "unlimited")
        max_ln = lim.get("max_lines", "unlimited")
        extra = ", single paragraph only" if lim.get("single_paragraph_only") else ""
        lines.append(
            f"- Section `## {name}`: max `{words}` words, max `{max_ln}` lines{extra}"
        )
    return lines


def _render_artifact_schema_block(
    artifact_type: str, schemas_policy: dict[str, Any]
) -> list[str]:
    """Render frontmatter schema and required Markdown section constraints."""
    artifact_rules = schemas_policy.get("artifacts", {}).get(artifact_type, {})
    schema_def = schemas_policy.get("schemas", {}).get(artifact_type, {})
    if not artifact_rules and not schema_def:
        return []
    lines = [f"### `{artifact_type}` Output Contract"]
    if schema_def:
        dumped = yaml.safe_dump(schema_def, sort_keys=False).strip()
        lines.extend(["```yaml", dumped, "```"])
    return [*lines, *_render_section_budgets(artifact_rules), ""]


def _render_glossary_constraints(repository_root: Path) -> list[str]:
    """Render canonical glossary terms and forbidden_synonyms."""
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if not glossary_path.exists():
        return []
    terms: list[dict[str, Any]] = load_yaml_file(glossary_path).get("terms", [])
    canonical_names = [str(item.get("canonical", "")) for item in terms]
    forbidden_pairs = [
        f"`{item.get('canonical')}` != "
        f"{', '.join(item.get('forbidden_synonyms', [])[:3])}"
        for item in terms
        if item.get("forbidden_synonyms")
    ]
    return [
        f"- **Canonical Terms**: {', '.join(canonical_names)}",
        f"- **Forbidden Synonyms**: {'; '.join(forbidden_pairs)}",
    ]


def _render_architecture_layers(repository_root: Path) -> list[str]:
    """Render defined layer names and path globs from policy/architecture.yaml."""
    arch_path = repository_root / "policy" / "architecture.yaml"
    if not arch_path.exists():
        return []
    layers = load_yaml_file(arch_path).get("layers", [])
    entries = [
        f"`{item.get('name')}` "
        f"({', '.join(str(item_path) for item_path in item.get('paths', []))})"
        for item in layers
        if isinstance(item, dict) and item.get("name")
    ]
    return [f"- **Architecture Layers**: {', '.join(entries)}"] if entries else []


def _render_code_and_glossary_section(
    repository_root: Path, agent_role: str
) -> list[str]:
    """Render architecture layers, sizing limits, AST rules, and glossary terms."""
    lines = [
        "## 3. Vocabulary & Engineering Constraints",
        *_render_architecture_layers(repository_root),
    ]
    if agent_role in {"worker-agent", "review-agent"}:
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
    return [*lines, *_render_glossary_constraints(repository_root), ""]


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
    repository_root: Path, heading_prefix: str, relative_path: str
) -> list[str]:
    """Render a Required File or Write File entry with inline content if present."""
    lines = [f"### {heading_prefix} `{relative_path}`", f"Path: `{relative_path}`"]
    file_path = repository_root / relative_path
    if file_path.is_file():
        lines.extend(["```python", file_path.read_text("utf-8").strip(), "```"])
    return [*lines, ""]


def _render_target_context_section(
    repository_root: Path,
    target_document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> list[str]:
    """Render target artifact, upstream artifacts, and required/write file contents."""
    lines = ["## 4. Scoped Target & Upstream Context", ""]
    for document in _collect_context_documents(target_document, by_identifier):
        artifact_id = str(document.frontmatter.get("id", document.path))
        raw = (repository_root / document.path).read_text("utf-8").strip()
        lines.extend(
            [
                f"### Artifact `{artifact_id}` (`{document.path}`)",
                f"Path: `{document.path}`",
                "```markdown",
                raw,
                "```",
                "",
            ]
        )
    for path in target_document.frontmatter.get("required_files", []):
        if (repository_root / str(path)).is_file():
            lines.extend(
                _render_code_file_block(repository_root, "Required File", str(path))
            )
    for path in target_document.frontmatter.get("write_files", []):
        lines.extend(_render_code_file_block(repository_root, "Write File", str(path)))
    return lines


def _assemble_prompt_sections(
    repository_root: Path,
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
    target_id: str | None = None,
) -> list[str]:
    """Assemble permissions, mission, execution steps, schemas, and vocabulary."""
    schemas_path = repository_root / "policy" / "schemas.yaml"
    schemas_policy = load_yaml_file(schemas_path) if schemas_path.exists() else {}
    primary_type = ROLE_TO_OUTPUT_SCHEMA.get(agent_role, "REQ")
    next_id = next_artifact_id(repository_root, primary_type)
    task_flag = (
        f"--task {target_id or '<task_id>'} " if agent_role == "worker-agent" else ""
    )
    verify_cmd = f"mt check all --agent {agent_role} {task_flag}--paths <written_files>"
    planner_hint = (
        f"- **Planner Decomposition Contract**: Author a `type: test_contract` Task "
        f"(`id: {next_id}`, `write_files` covering `SPEC` `target_files.tests`, "
        "`verification_cmd: python3 -m py_compile <test_file>`) and "
        f"`type: implementation` Task(s) (`depends_on: [{next_id}]`, `write_files` "
        "covering `SPEC` `target_files.implementation`, "
        "`verification_cmd: pytest -q <test_file>`)."
    )
    lines = [
        *_render_permissions_section(agent_role, role_configuration, global_forbidden),
        f"**Mission**: {_find_role_definition(repository_root, agent_role)}",
        f"- **Assigned Next Artifact ID**: `{next_id}` (auto-normalized on merge)",
        "- **Self-Contained Context**: All required Policy schemas, section budgets, "
        "Architecture layers, Glossary terms, and upstream artifacts are provided "
        "below in this document.",
        "- **Execution Steps**:",
        "  1. Author the target file(s) in `Allowed Write` directly from the "
        "schemas, constraints, and context below.",
        f"  2. Verify the written file(s) by running `{verify_cmd}` "
        "(and `verification_cmd` for `worker-agent`) once.",
        "  3. Finish and return a brief summary immediately once verification "
        "exits with code `0` and empty `stdout` (`MergeGate` runs on exit).",
        *([planner_hint] if agent_role == "planner-agent" else []),
        "",
        "## 2. Output Schemas & Section Budgets",
        *_render_artifact_schema_block(primary_type, schemas_policy),
    ]
    if role_configuration.get("escalation_write"):
        lines.extend(_render_artifact_schema_block("ESC", schemas_policy))
    lines.extend(_render_code_and_glossary_section(repository_root, agent_role))
    return lines


def build_agent_prompt(
    repository_root: Path,
    agent_role: str,
    target_id: str | None = None,
) -> tuple[str, list[Finding]]:
    """Synthesize a deterministic self-contained role prompt from policy and target."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    agents: dict[str, Any] = permissions.get("agents", {})
    if agent_role not in agents:
        message = f"Unknown agent role '{agent_role}'."
        return "", [
            Finding("policy/permissions.yaml", 1, "CLI_UNKNOWN_AGENT_ROLE", message)
        ]
    by_id = load_artifacts_by_id(repository_root)
    target_doc = by_id.get(target_id) if target_id else None
    if target_id is not None and target_doc is None:
        message = f"Target artifact '{target_id}' not found."
        return "", [Finding(target_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    forbidden = [str(item) for item in permissions.get("global_forbidden_write", [])]
    lines = _assemble_prompt_sections(
        repository_root, agent_role, agents[agent_role], forbidden, target_id
    )
    if target_doc is not None:
        lines.extend(_render_target_context_section(repository_root, target_doc, by_id))
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
    template = environments.get(environment_name)
    return (str(template) if template else None), environment_name, model_name


def prepare_worker_invocation(
    worktree_path: Path,
    document: ArtifactDocument,
    prompt_file: Path,
    execution_context: tuple[str, str, str],
) -> tuple[str, dict[str, str]]:
    """Write .mt_prompt.md and build command and environment for worker execution."""
    task_id = str(document.frontmatter["id"])
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    prompt_text, _ = build_agent_prompt(worktree_path, "worker-agent", task_id)
    prompt_file.write_text(prompt_text, encoding="utf-8")
    command_template, environment_name, model_name = execution_context
    rendered_command = (
        command_template.replace("{model}", model_name)
        .replace("{task_id}", task_id)
        .replace("{prompt_file}", str(prompt_file))
    )
    environment = {
        **os.environ,
        "PYTHONPATH": str(worktree_path),
        "MT_AGENT_ROLE": "worker-agent",
        "MT_TASK_ID": task_id,
        "MT_WRITE_FILES": ",".join(write_files),
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
    }
    return rendered_command, environment
