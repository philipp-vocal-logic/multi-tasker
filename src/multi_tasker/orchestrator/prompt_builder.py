"""Deterministic self-contained role prompt synthesizer from policies and artifacts."""

import os
from pathlib import Path
from typing import Any

from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import (
    load_artifacts_by_id,
    load_yaml_file,
    next_artifact_id,
)
from multi_tasker.orchestrator.prompt_context import (
    MAX_PROMPT_LINE_LENGTH,
    find_role_definition,
    load_artifact_schemas_and_limits,
    render_code_and_glossary_section,
    render_decomposition_contract,
    render_target_context_section,
    wrap_prompt_lines,
)

__all__ = [
    "MAX_PROMPT_LINE_LENGTH",
    "build_agent_prompt",
    "prepare_worker_invocation",
    "resolve_task_execution",
]

ROLE_TO_OUTPUT_SCHEMA: dict[str, str] = {
    "requirement-agent": "REQ",
    "specification-agent": "SPEC",
    "planner-agent": "TASK",
    "review-agent": "REV",
}

ROLE_OUTPUT_DIR: dict[str, str] = {
    "REQ": "artifacts/requirements",
    "SPEC": "artifacts/specifications",
    "REV": "artifacts/reviews",
}

ROLE_TARGET_STATUS: dict[str, str] = {
    "requirement-agent": "status: in_review",
    "specification-agent": "status: in_review",
    "planner-agent": "status: ready",
    "review-agent": "verdict: pass|fail",
}


def _resolve_rule_write_path(
    rule: dict[str, Any], target_doc: ArtifactDocument | None
) -> str:
    """Expand $TASK_WRITE_FILES to target_doc write_files when available."""
    raw_path = str(rule.get("path", ""))
    if raw_path == "$TASK_WRITE_FILES" and target_doc is not None:
        writes = [str(item) for item in target_doc.frontmatter.get("write_files", [])]
        if writes:
            return ", ".join(writes)
    return raw_path


def _render_permissions_section(
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
    target_doc: ArtifactDocument | None = None,
    escalation_routes: dict[str, Any] | None = None,
) -> list[str]:
    """Render WriteScope, state transitions, and escalation rules for agent_role."""
    lines = [
        f"# Role Prompt: `{agent_role}`",
        "",
        "## 1. WriteScope & Permission Contract",
        f"- **Global Forbidden Writes**: `{', '.join(global_forbidden) or 'none'}`",
    ]
    for rule in role_configuration.get("allowed_write", []):
        path = _resolve_rule_write_path(rule, target_doc)
        existing = ", ".join(
            str(state) for state in rule.get("allowed_existing_states", [])
        )
        targets = ", ".join(
            str(state) for state in rule.get("allowed_target_states", [])
        )
        lines.append(
            f"- **Allowed Write**: `{path}` "
            f"(existing: `{existing or 'task-scoped'}` -> target: `{targets or 'any'}`)"
        )
    escalation_rules = role_configuration.get("escalation_write", [])
    if escalation_rules:
        paths = ", ".join(f"`{rule.get('path', '')}`" for rule in escalation_rules)
        routes = ", ".join(
            f"`{cat}` -> `{cfg.get('target_actor', 'human')}`"
            for cat, cfg in (escalation_routes or {}).items()
            if isinstance(cfg, dict)
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


def _format_property_hint(key: str, prop: dict[str, Any], artifact_type: str) -> str:
    """Format a compact single-line frontmatter field hint with non-fixed IDs."""
    if key == "id":
        return f"id: {artifact_type}-NNN"
    if key == "status" and "ready" in prop.get("enum", []):
        return "status: ready"
    if key == "status" and "in_review" in prop.get("enum", []):
        return "status: in_review"
    if key == "acceptance_criteria":
        return "acceptance_criteria: [{id: AC-XX, given: ..., when: ..., then: ...}]"
    if key == "target_files":
        return "target_files: {tests: [tests/...], implementation: [src/...]}"
    if "enum" in prop:
        return f"{key}: {'|'.join(str(val) for val in prop['enum'])}"
    if prop.get("type") == "array":
        pattern = prop.get("items", {}).get("pattern", "...")
        return f"{key}: [{pattern}]"
    return f"{key}: <{prop.get('type', 'value')}>"


def _render_artifact_schema_block(
    artifact_type: str, schemas_policy: dict[str, Any]
) -> list[str]:
    """Render compact Markdown frontmatter + section skeleton and section budgets."""
    artifact_rules = schemas_policy.get("artifacts", {}).get(artifact_type, {})
    schema_def = schemas_policy.get("schemas", {}).get(artifact_type, {})
    if not artifact_rules and not schema_def:
        return []
    json_schema = schema_def.get("json_schema", {})
    props = json_schema.get("properties", {})
    req_keys = json_schema.get("required", list(props.keys()))
    fm_lines = [
        _format_property_hint(str(key), props.get(str(key), {}), artifact_type)
        for key in req_keys
    ]
    sec_lines = [
        f"## {sec}\n<content>" for sec in artifact_rules.get("required_sections", [])
    ]
    skeleton = ["```markdown", "---", *fm_lines, "---", *sec_lines, "```"]
    return [
        f"### `{artifact_type}` Output Contract (`{schema_def.get('path_glob', '')}`)",
        *skeleton,
        *_render_section_budgets(artifact_rules),
        "",
    ]


def _render_worker_code_contract() -> list[str]:
    """Render Python Source and TestContract output skeleton for worker-agent."""
    return [
        "### Python Source & `TestContract` Output Contract (`Allowed Write`)",
        "```python",
        '"""Single-paragraph module docstring within max_docstring_lines/words."""',
        "",
        "from multi_tasker.domain.models import traces",
        "",
        "",
        '@traces("REQ-NNN", "AC-XX", "SPEC-NNN")',
        "def test_example_behavior() -> None:",
        '    """Single-paragraph docstring (return type, names >= 3 chars)."""',
        "    expected_value = 1",
        "    assert expected_value == 1",
        "```",
        "- **Scope & Imports**: Create or update only the exact path(s) in "
        "`Allowed Write` (parent directories are created automatically; `src` and `.` "
        "are on `PYTHONPATH`, so namespace imports work without extra `__init__.py` "
        "files).",
        "- **Docstrings & Types**: Keep every module, class, and function docstring "
        "within `max_docstring_lines` and `max_docstring_words`; declare explicit "
        "return types (`-> None`, `-> int`, etc.) and use identifiers "
        "`>= min_identifier_length` chars.",
        "",
    ]


def _render_escalation_contract(
    agent_role: str, schemas_policy: dict[str, Any]
) -> list[str]:
    """Render a compact Escalation output contract with non-fixed ESC-NNN ID."""
    esc_rules = schemas_policy.get("artifacts", {}).get("ESC", {})
    return [
        "### `ESC` Output Contract (`artifacts/escalations/ESC-*.md`)",
        f"- **Frontmatter**: `id: ESC-NNN`, `source_agent: {agent_role}`, "
        "`task_or_stage: <ID>`, `affected_artifacts: [<ID>]`, "
        "`reason_category: ambiguity|rule_conflict|infeasible_scope|"
        "test_contract_defect|review_exhausted`, `status: open`, `resolved_by: null`",
        *_render_section_budgets(esc_rules),
        "",
    ]


def _resolve_stage_write_paths(
    agent_role: str,
    target_doc: ArtifactDocument | None,
    next_id: str | None,
) -> str:
    """Resolve concrete verification file paths for worker-agent or stage agents."""
    if target_doc and target_doc.frontmatter.get("write_files"):
        return " ".join(str(item) for item in target_doc.frontmatter["write_files"])
    primary_type = ROLE_TO_OUTPUT_SCHEMA.get(agent_role, "")
    output_dir = ROLE_OUTPUT_DIR.get(primary_type, "")
    if target_doc is not None and output_dir and next_id:
        if target_doc.artifact_type == primary_type:
            return target_doc.path
        return f"{output_dir}/{next_id}.md"
    return "<written_files>"


def _build_execution_steps(
    agent_role: str,
    target_doc: ArtifactDocument | None,
    next_id: str | None,
) -> list[str]:
    """Build concrete role-specific 3-step Execution Steps for agent_role."""
    target_id = str(target_doc.frontmatter.get("id", "")) if target_doc else "<task_id>"
    write_paths = _resolve_stage_write_paths(agent_role, target_doc, next_id)
    raw_cmd = target_doc.frontmatter.get("verification_cmd", "") if target_doc else ""
    ver_cmd = str(raw_cmd).strip()
    task_flag = f"--task {target_id} " if agent_role == "worker-agent" else ""
    suffix = f" && {ver_cmd}" if agent_role == "worker-agent" and ver_cmd else ""
    verify_cmd = (
        f"mt check all --agent {agent_role} {task_flag}--paths {write_paths}{suffix}"
    )
    role_status = ROLE_TARGET_STATUS.get(agent_role, "")
    status_hint = f" (`{role_status}`)" if role_status and next_id is not None else ""
    return [
        "- **Execution Steps**:",
        f"  1. Author the target file(s) in `Allowed Write`{status_hint} directly "
        "from the template, constraints, and inlined context below.",
        f"  2. Verify once by running `{verify_cmd}`.",
        "  3. Finish and return a brief summary immediately once Step 2 exits with "
        "code `0` and empty `mt check` stdout (`MergeGate` commits on exit).",
    ]


def _resolve_next_prompt_id(
    repository_root: Path,
    primary_type: str | None,
    target_doc: ArtifactDocument | None,
) -> str | None:
    """Return concrete next_artifact_id for targeted runs or <TYPE>-NNN for examples."""
    if not primary_type:
        return None
    if target_doc is not None:
        return next_artifact_id(repository_root, primary_type)
    return f"{primary_type}-NNN"


def _assemble_prompt_sections(
    repository_root: Path,
    agent_role: str,
    role_configuration: dict[str, Any],
    global_forbidden: list[str],
    target_doc: ArtifactDocument | None = None,
) -> list[str]:
    """Assemble permissions, mission, execution steps, schemas, and vocabulary."""
    schemas_policy = load_artifact_schemas_and_limits(repository_root)
    primary_type = ROLE_TO_OUTPUT_SCHEMA.get(agent_role)
    next_id = _resolve_next_prompt_id(repository_root, primary_type, target_doc)
    output_contract = (
        _render_artifact_schema_block(primary_type, schemas_policy)
        if primary_type
        else _render_worker_code_contract()
    )
    lines = [
        *_render_permissions_section(
            agent_role,
            role_configuration,
            global_forbidden,
            target_doc,
            schemas_policy.get("escalation_routes", {}),
        ),
        f"**Mission**: {find_role_definition(repository_root, agent_role)}",
        *(
            [f"- **Assigned Next Artifact ID**: `{next_id}` (auto-normalized on merge)"]
            if next_id
            else []
        ),
        "- **Self-Contained Context**: All required Policy schemas, section budgets, "
        "Architecture layers, Glossary terms, and upstream artifacts are provided "
        "below in this document.",
        *_build_execution_steps(agent_role, target_doc, next_id),
        *render_decomposition_contract(agent_role, next_id),
        "",
        "## 2. Output Schemas & Section Budgets",
        *output_contract,
    ]
    if role_configuration.get("escalation_write"):
        lines.extend(_render_escalation_contract(agent_role, schemas_policy))
    lines.extend(render_code_and_glossary_section(repository_root, agent_role))
    return wrap_prompt_lines(lines)


def build_agent_prompt(
    repository_root: Path,
    agent_role: str,
    target_id: str | None = None,
) -> tuple[str, list[Finding]]:
    """Synthesize a deterministic self-contained role prompt from policy and target."""
    permissions_path = repository_root / "policy" / "agent_permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    agents: dict[str, Any] = permissions.get("agents", {})
    if agent_role not in agents:
        message = f"Unknown agent role '{agent_role}'."
        return "", [
            Finding(
                "policy/agent_permissions.yaml", 1, "CLI_UNKNOWN_AGENT_ROLE", message
            )
        ]
    by_id = load_artifacts_by_id(repository_root)
    target_doc = by_id.get(target_id) if target_id else None
    if target_id is not None and target_doc is None:
        message = f"Target artifact '{target_id}' not found."
        return "", [Finding(target_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    forbidden = [str(item) for item in permissions.get("global_forbidden_write", [])]
    lines = _assemble_prompt_sections(
        repository_root, agent_role, agents[agent_role], forbidden, target_doc
    )
    if target_doc is not None:
        lines.extend(render_target_context_section(repository_root, target_doc, by_id))
    return "\n".join(lines).strip() + "\n", []


def resolve_task_execution(
    repository_root: Path,
    document: ArtifactDocument,
    options: tuple[str | None, str | None, str | None] = (None, None, None),
    agent_role: str = "worker-agent",
) -> tuple[str | None, str, str]:
    """Resolve (command_template, environment_name, model_name) for an agent run."""
    agent_command, model_override, environment_override = options
    execution_path = repository_root / "policy" / "agent_execution.yaml"
    execution = load_yaml_file(execution_path) if execution_path.exists() else {}
    execution_config: dict[str, Any] = execution.get("execution_environments", {})
    role_config: dict[str, Any] = execution.get("agents", {}).get(agent_role, {})
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
        "PYTHONPATH": f"{worktree_path / 'src'}{os.pathsep}{worktree_path}",
        "MT_AGENT_ROLE": "worker-agent",
        "MT_TASK_ID": task_id,
        "MT_WRITE_FILES": ",".join(write_files),
        "MT_PROMPT_FILE": str(prompt_file),
        "MT_AGENT_MODEL": model_name,
        "MT_EXECUTION_ENVIRONMENT": environment_name,
    }
    return rendered_command, environment
