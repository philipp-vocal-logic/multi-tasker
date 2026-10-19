"""Deterministic Markdown documentation and Mermaid diagram generator."""

from pathlib import Path
from typing import Any

from multi_tasker.domain.models import ArtifactDocument
from multi_tasker.domain.parser import (
    load_artifacts_by_id,
    load_state_transitions,
    load_yaml_file,
)
from multi_tasker.orchestrator.lineage import (
    group_artifacts_by_intent,
    render_test_and_coverage_section,
)
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt


def _render_architecture_section(repository_root: Path) -> list[str]:
    """Render architecture layers table and Mermaid dependency flowchart."""
    policy_path = repository_root / "policy" / "architecture.yaml"
    policy = load_yaml_file(policy_path) if policy_path.exists() else {}
    layers: list[dict[str, Any]] = policy.get("layers", [])
    lines = [
        "## 1. Architecture & Layer Boundaries",
        "",
        "| Layer | Paths | Allowed Internal Imports |",
        "| :--- | :--- | :--- |",
    ]
    for layer in layers:
        name = str(layer.get("name", ""))
        paths = ", ".join(f"`{item}`" for item in layer.get("paths", []))
        allowed = ", ".join(
            f"`{item}`" for item in layer.get("allowed_internal_imports", [])
        )
        lines.append(f"| **{name}** | {paths} | {allowed} |")
    lines.extend(["", "```mermaid", "flowchart TD"])
    for layer in layers:
        source_name = str(layer.get("name", ""))
        for target_prefix in layer.get("allowed_internal_imports", []):
            target_name = str(target_prefix).split(".")[-1]
            if target_name and target_name != source_name:
                edge = f'    {source_name}["{source_name}"]'
                lines.append(f'{edge} --> {target_name}["{target_name}"]')
    lines.extend(["```", ""])
    return lines


def _render_permissions_section(repository_root: Path) -> list[str]:
    """Render agent WriteScope permissions table from policy/permissions.yaml."""
    policy_path = repository_root / "policy" / "permissions.yaml"
    policy = load_yaml_file(policy_path) if policy_path.exists() else {}
    agents: dict[str, Any] = policy.get("agents", {})
    header = (
        "| Agent Role | Allowed Write Paths | Allowed Existing States "
        "| Escalation Write |"
    )
    lines = [
        "## 2. Agent WriteScope & Permission Topology",
        "",
        header,
        "| :--- | :--- | :--- | :--- |",
    ]
    for role_name, configuration in agents.items():
        write_rules = configuration.get("allowed_write", [])
        paths = ", ".join(f"`{rule.get('path', '')}`" for rule in write_rules)
        states = (
            ", ".join(
                str(state)
                for rule in write_rules
                for state in rule.get("allowed_existing_states", [])
            )
            or "Task-scoped"
        )
        escalation_rules = configuration.get("escalation_write", [])
        escalation = (
            ", ".join(f"`{rule.get('path', '')}`" for rule in escalation_rules)
            or "None"
        )
        lines.append(f"| `{role_name}` | {paths} | {states} | {escalation} |")
    lines.append("")
    return lines


def _render_state_lifecycles_section(repository_root: Path) -> list[str]:
    """Render Mermaid stateDiagram-v2 blocks from policy/schemas.yaml."""
    transitions = load_state_transitions(repository_root)
    lines = ["## 3. Artifact State Lifecycles", ""]
    for artifact_type, mapping in sorted(transitions.items()):
        lines.extend(
            [
                f"### {artifact_type} State Machine",
                "",
                "```mermaid",
                "stateDiagram-v2",
            ]
        )
        for source_state, targets in sorted(mapping.items()):
            for target_state in sorted(targets):
                lines.append(f"    {source_state} --> {target_state}")
        lines.extend(["```", ""])
    return lines


def _render_limits_and_glossary_section(repository_root: Path) -> list[str]:
    """Render source code sizing limits and canonical domain glossary table."""
    limits_path = repository_root / "policy" / "limits.yaml"
    limits_policy = load_yaml_file(limits_path) if limits_path.exists() else {}
    source_limits: dict[str, Any] = limits_policy.get("source_code", {})
    glossary_path = repository_root / "policy" / "glossary.yaml"
    glossary_policy = load_yaml_file(glossary_path) if glossary_path.exists() else {}
    terms: list[dict[str, Any]] = glossary_policy.get("terms", [])
    lines = [
        "## 4. Source Code Sizing Limits & Domain Glossary",
        "",
        "| Limit Key | Value |",
        "| :--- | :--- |",
    ]
    for key, value in sorted(source_limits.items()):
        lines.append(f"| `{key}` | `{value}` |")
    lines.extend(
        [
            "",
            "| Canonical Term | Category | Forbidden Synonyms |",
            "| :--- | :--- | :--- |",
        ]
    )
    for entry in terms:
        canonical = str(entry.get("canonical", ""))
        category = str(entry.get("category", ""))
        synonyms = ", ".join(
            f"`{item}`" for item in entry.get("forbidden_synonyms", [])[:5]
        )
        lines.append(f"| **{canonical}** | `{category}` | {synonyms} |")
    lines.append("")
    return lines


def _append_artifact_trace_edges(
    by_identifier: dict[str, ArtifactDocument], lines: list[str]
) -> None:
    """Append Mermaid flowchart nodes and edges for a subgraph of artifacts."""
    for artifact_id, document in sorted(by_identifier.items()):
        title = str(
            document.frontmatter.get(
                "title", document.frontmatter.get("stage", document.artifact_type)
            )
        )
        status = str(
            document.frontmatter.get(
                "status", document.frontmatter.get("verdict", "ok")
            )
        )
        safe_id = artifact_id.replace("-", "_")
        lines.append(f'    {safe_id}["{artifact_id}: {title} ({status})"]')
        for upstream in document.frontmatter.get("traces_to", []):
            if str(upstream) in by_identifier:
                upstream_safe = str(upstream).replace("-", "_")
                lines.append(f"    {upstream_safe} --> {safe_id}")
        for dependency in (
            *document.frontmatter.get("depends_on", []),
            *document.frontmatter.get("target_artifacts", []),
        ):
            if str(dependency) in by_identifier:
                dependency_safe = str(dependency).replace("-", "_")
                lines.append(f"    {dependency_safe} -.-> {safe_id}")


def _render_traceability_section(repository_root: Path) -> list[str]:
    """Render per-Intent Mermaid traceability subgraphs and unlinked fallback."""
    by_identifier = load_artifacts_by_id(repository_root)
    groups = group_artifacts_by_intent(by_identifier)
    lines = ["## 5. Live Repository Traceability Graph", ""]
    if not groups:
        lines.extend(["```mermaid", "flowchart TD", "```", ""])
        return lines
    for heading, subgraph_docs in groups:
        lines.extend([f"### {heading}", "", "```mermaid", "flowchart TD"])
        _append_artifact_trace_edges(subgraph_docs, lines)
        lines.extend(["```", ""])
    return lines


def _render_pipeline_section(repository_root: Path) -> list[str]:
    """Render Declarative Agent Pipeline & Escalation Routing Mermaid flowchart."""
    pipeline_path = repository_root / "policy" / "pipeline.yaml"
    policy = load_yaml_file(pipeline_path) if pipeline_path.exists() else {}
    bounds: dict[str, Any] = policy.get("execution_bounds", {})
    stages: list[dict[str, Any]] = policy.get("stages", [])
    routes: dict[str, Any] = policy.get("escalation_routes", {})
    bounds_summary = ", ".join(f"`{key}={val}`" for key, val in sorted(bounds.items()))
    lines = [
        "## 6. Declarative Agent Pipeline & Escalation Routing",
        "",
        f"- **Execution Bounds**: {bounds_summary or 'default'}",
        "",
        "```mermaid",
        "flowchart TD",
    ]
    for stage in stages:
        stage_id = str(stage.get("id", ""))
        trigger = str(stage.get("trigger_type", ""))
        states = ", ".join(str(item) for item in stage.get("trigger_states", []))
        role = str(stage.get("agent_role", ""))
        gate = str(stage.get("approval_gate", ""))
        downstream = str(stage.get("downstream_type", ""))
        role_id = role.replace("-", "_")
        role_node = f'{role_id}["{role} (gate: {gate})"]'
        lines.append(
            f'    {trigger}["{trigger} ({states})"] -->|"{stage_id}"| {role_node}'
        )
        lines.append(f'    {role_id} --> {downstream}["{downstream}"]')
    for category, route in sorted(routes.items()):
        actor = str(route.get("target_actor", ""))
        action = str(route.get("action", ""))
        next_status = str(route.get("next_status", ""))
        actor_id = actor.replace("-", "_")
        lines.append(
            f'    ESC_{category}["ESC: {category}"] '
            f'-.->|"{action} ({next_status})"| {actor_id}["{actor}"]'
        )
    lines.extend(["```", ""])
    return lines


def _render_example_prompts_section(repository_root: Path) -> list[str]:
    """Render collapsible 4-backtick role prompt examples for all configured roles."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path) if permissions_path.exists() else {}
    role_names = list(permissions.get("agents", {}).keys())
    lines = ["## 7. Generated Example Agent Instructions", ""]
    for role_name in role_names:
        prompt_text, _ = build_agent_prompt(repository_root, str(role_name))
        lines.extend(
            [
                "<details>",
                f"<summary>Role Prompt: <code>{role_name}</code></summary>",
                "",
                "````markdown",
                prompt_text.strip(),
                "````",
                "",
                "</details>",
                "",
            ]
        )
    return lines


def generate_repository_documentation(repository_root: Path) -> str:
    """Generate complete Markdown specification and diagrams from live repo state."""
    sections = [
        "# Incremental Multilevel Agent System — Generated Live Specification",
        "",
        *_render_architecture_section(repository_root),
        *_render_permissions_section(repository_root),
        *_render_state_lifecycles_section(repository_root),
        *_render_limits_and_glossary_section(repository_root),
        *_render_traceability_section(repository_root),
        *_render_pipeline_section(repository_root),
        *_render_example_prompts_section(repository_root),
        *render_test_and_coverage_section(repository_root),
    ]
    return "\n".join(sections).strip() + "\n"


def write_repository_documentation(repository_root: Path) -> Path:
    """Generate live specification Markdown and write .report/specification.md."""
    report_directory = repository_root / ".report"
    report_directory.mkdir(parents=True, exist_ok=True)
    (report_directory / ".gitignore").write_text("*\n", encoding="utf-8")
    report_path = report_directory / "specification.md"
    report_path.write_text(
        generate_repository_documentation(repository_root), encoding="utf-8"
    )
    return report_path


def generate_external_agents_guide() -> str:
    """Synthesize external project AGENTS.md bootstrapping and policy tuning guide."""
    lines = [
        "# AGENTS.md — External Project Bootstrapping & Development Guide",
        "",
        "## 1. One-Time Bootstrapping & Tailoring Policy Configuration",
        "1. **Install & Initialize**: Install `multi-tasker` (`pip install -e <path>`) "
        "and run `mt initialize`.",
        "2. **Customize Architecture & Vocabulary (`policy/architecture.yaml`, "
        "`policy/glossary.yaml`)**:",
        "   - Replace `layers` (`paths`, `allowed_internal_imports`, "
        "`forbidden_internal_imports`) and `allowed_third_party_packages` (keep "
        "'\"multi_tasker\"' and '\"pytest\"').",
        "   - Keep core `mt` orchestration terms and agent roles in "
        "`policy/glossary.yaml` and append project domain terms.",
        "3. **Tune Use-Case Policies (`policy/pipeline.yaml`, "
        "`policy/permissions.yaml`, `policy/clean_code.yaml`, "
        "`policy/limits.yaml`, `policy/schemas.yaml`)**:",
        "   - Configure stage `approval_gate` (`human`, `review-agent`, `auto`), "
        "`execution_environments`, per-role `model`, `ast_rules`, and sizing bounds.",
        "4. **Commit Baseline Policies (`PERM_POLICY_MODIFIED` Rule)**: Uncommitted "
        "`policy/**` edits fail `mt check permissions` and `policy/` is read-only in "
        "`Worktrees`. Run `mt intent 'Bootstrap project policies'` (`INT-001`) and "
        "commit `INT-001: Bootstrap project policies [traces: INT-001]` before "
        "running `mt check all` or `mt run`.",
        "",
        "## 2. Mandatory Artifact Lifecycle Workflow",
        "Never edit `src/**`, `tests/**`, `policy/**`, or `done` `TASK-NNN.md` files "
        "ad-hoc:",
        "1. `mt intent '<what to change and why>'` -> `artifacts/intents/INT-NNN.md`.",
        "2. Author `artifacts/requirements/REQ-NNN.md` -> `mt approve REQ-NNN`.",
        "3. Author `artifacts/specifications/SPEC-NNN.md` -> `mt approve SPEC-NNN`.",
        "4. Author `artifacts/tasks/TASK-NNN.md`: `test_contract` importing "
        "`from multi_tasker.domain.models import traces` (`@traces(...)`) followed by "
        "`implementation` Tasks.",
        "5. Execute via `mt run`, `mt run --agent <role> --target <id>`, or "
        "`mt run --pipeline`, and verify `mt check all` exits `0` with empty `stdout`.",
    ]
    return "\n".join(lines) + "\n"
