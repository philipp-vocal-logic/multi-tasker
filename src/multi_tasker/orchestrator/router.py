"""Deterministic tiered Escalation router driven by policy/pipeline.yaml."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from multi_tasker.checkers.runner import run_checks
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import (
    load_artifacts_by_id,
    load_pipeline_policy,
    load_state_transitions,
    parse_artifact_file,
    update_artifact_frontmatter,
)
from multi_tasker.orchestrator.scheduler import (
    compute_dirty_subgraph,
    select_parallel_batch,
)
from multi_tasker.orchestrator.worktree import (
    commit_traceable_change,
    merge_worktree_files,
)


@dataclass(frozen=True)
class RouteDecision:
    """Deterministic routing outcome for an Escalation artifact."""

    escalation_id: str
    target_actor: str
    next_status: str
    action: str


def _load_routing_table(
    repository_root: Path,
) -> tuple[dict[str, tuple[str, str, str]], int]:
    """Load escalation_routes and max_auto_reroutes from artifact_lifecycle.yaml."""
    pipeline = load_pipeline_policy(repository_root)
    bounds: dict[str, Any] = pipeline.get("execution_bounds", {})
    max_reroutes = int(bounds.get("max_auto_reroutes", 1))
    raw_routes: dict[str, Any] = pipeline.get("escalation_routes", {})
    routes = {
        str(category): (
            str(entry.get("target_actor", "human")),
            str(entry.get("next_status", "awaiting_human")),
            str(entry.get("action", "require_decision")),
        )
        for category, entry in raw_routes.items()
        if isinstance(entry, dict)
    }
    return routes, max_reroutes


def _count_prior_reroutes(
    repository_root: Path, escalation_id: str, task_or_stage: str
) -> int:
    """Count existing routed or resolved Escalations for the same task_or_stage."""
    if not task_or_stage:
        return 0
    return sum(
        1
        for identifier, document in load_artifacts_by_id(repository_root).items()
        if document.artifact_type == "ESC"
        and identifier != escalation_id
        and str(document.frontmatter.get("task_or_stage", "")) == task_or_stage
        and str(document.frontmatter.get("status", ""))
        in {"routed_to_agent", "resolved"}
    )


def route_escalation(
    repository_root: Path, escalation_relative_path: str, prior_reroutes: int = 0
) -> RouteDecision:
    """Route an Escalation by reason_category with policy-configured max reroutes."""
    absolute_path = repository_root / escalation_relative_path
    document, findings = parse_artifact_file(absolute_path, escalation_relative_path)
    if findings or document is None:
        return RouteDecision("UNKNOWN", "human", "awaiting_human", "invalid_escalation")
    escalation_id = str(document.frontmatter.get("id", "UNKNOWN"))
    category = str(document.frontmatter.get("reason_category", "ambiguity"))
    task_or_stage = str(document.frontmatter.get("task_or_stage", ""))
    routes, max_reroutes = _load_routing_table(repository_root)
    effective_reroutes = max(
        prior_reroutes,
        _count_prior_reroutes(repository_root, escalation_id, task_or_stage),
    )
    if effective_reroutes >= max_reroutes:
        return RouteDecision(
            escalation_id, "human", "awaiting_human", "reroute_limit_reached"
        )
    actor, status, action = routes.get(
        category, ("human", "awaiting_human", "require_decision")
    )
    return RouteDecision(escalation_id, actor, status, action)


def find_actionable_stage_target(
    repository_root: Path, stage: dict[str, Any]
) -> str | None:
    """Return the first actionable artifact ID for stage, or None."""
    trigger_type = str(stage.get("trigger_type", ""))
    if trigger_type == "TASK":
        batch, _ = select_parallel_batch(repository_root)
        return batch[0] if batch else None
    trigger_states = {str(item) for item in stage.get("trigger_states", [])}
    downstream_type = str(stage.get("downstream_type", ""))
    by_id = load_artifacts_by_id(repository_root)
    failed_targets = {
        str(target)
        for doc in by_id.values()
        if doc.artifact_type == "REV" and doc.frontmatter.get("verdict") == "fail"
        for target in doc.frontmatter.get("target_artifacts", [])
    }
    retry_pending = {
        doc_id
        for doc_id, doc in by_id.items()
        if doc_id in failed_targets
        and str(doc.frontmatter.get("status", "")) in {"draft", "blocked"}
    }
    covered = {
        str(upstream)
        for doc_id, doc in by_id.items()
        if doc.artifact_type == downstream_type and doc_id not in retry_pending
        for upstream in doc.frontmatter.get("traces_to", [])
    }
    for artifact_id, doc in sorted(by_id.items()):
        state = str(doc.frontmatter.get("status", ""))
        if (
            doc.artifact_type == trigger_type
            and state in trigger_states
            and (state == "needs_update" or artifact_id not in covered)
        ):
            return artifact_id
    return None


def check_transition(
    repository_root: Path, document: ArtifactDocument, target_state: str
) -> list[Finding]:
    """Validate artifact status transition against schemas or permissions policy."""
    current_state = str(document.frontmatter.get("status", ""))
    if not current_state:
        return []
    transitions = load_state_transitions(repository_root)
    allowed = transitions.get(document.artifact_type, {}).get(current_state)
    if isinstance(allowed, set) and target_state not in allowed:
        message = f"Invalid state transition '{current_state}' -> '{target_state}'."
        return [Finding(document.path, 1, "PERM_INVALID_STATE_TRANSITION", message)]
    return []


def _create_review_escalation(
    repository_root: Path, artifact_id: str, rev_path: str
) -> list[Finding]:
    """Create an awaiting_human review_exhausted Escalation and block artifact_id."""
    by_id = load_artifacts_by_id(repository_root)
    esc_nums = [
        int(key.split("-")[1])
        for key in by_id
        if key.startswith("ESC-") and key.split("-")[1].isdigit()
    ]
    esc_id = f"ESC-{max(esc_nums, default=0) + 1:03d}"
    esc_rel = f"artifacts/escalations/{esc_id}.md"
    (repository_root / esc_rel).write_text(
        f"---\nid: {esc_id}\nsource_agent: orchestrator\n"
        f"task_or_stage: {artifact_id}\naffected_artifacts: [{artifact_id}]\n"
        "reason_category: review_exhausted\nstatus: awaiting_human\n"
        "resolved_by: null\n---\n"
        f"## Blocking Problem\nReview cycles exhausted for {artifact_id}.\n",
        encoding="utf-8",
    )
    target_doc = by_id.get(artifact_id)
    if target_doc is not None:
        update_artifact_frontmatter(
            repository_root / target_doc.path, {"status": "blocked"}
        )
    changed = [
        esc_rel,
        *([target_doc.path] if target_doc is not None else []),
    ]
    subject = (
        f"{esc_id}: Escalate {artifact_id} review [traces: {artifact_id}, {esc_id}]"
    )
    commit_traceable_change(repository_root, changed, subject)
    message = f"Review cycles exhausted for '{artifact_id}' ({esc_id})."
    return [Finding(rev_path, 1, "STAGE_REVIEW_EXHAUSTED", message)]


def evaluate_review_verdict(
    repository_root: Path, artifact_id: str, rev_id: str
) -> list[Finding]:
    """Check REV verdict for artifact_id and emit Finding or escalation on fail."""
    by_id = load_artifacts_by_id(repository_root)
    rev_doc = by_id.get(rev_id)
    if rev_doc is None or rev_doc.frontmatter.get("verdict") == "pass":
        return []
    fail_count = sum(
        1
        for doc in by_id.values()
        if doc.artifact_type == "REV"
        and doc.frontmatter.get("verdict") == "fail"
        and artifact_id
        in {str(item) for item in doc.frontmatter.get("target_artifacts", [])}
    )
    bounds = load_pipeline_policy(repository_root).get("execution_bounds", {})
    if fail_count >= int(bounds.get("max_review_cycles", 2)):
        return _create_review_escalation(repository_root, artifact_id, rev_doc.path)
    message = f"Review '{rev_id}' rejected '{artifact_id}'."
    return [Finding(rev_doc.path, 1, "STAGE_REVIEW_REJECTED", message)]


def _mark_dirty_subgraph(
    repository_root: Path,
    by_identifier: dict[str, ArtifactDocument],
    changed_id: str,
) -> None:
    """Mark downstream approved SPEC and done TASK artifacts as needs_update."""
    for dirty_id in compute_dirty_subgraph(repository_root, changed_id):
        doc = by_identifier.get(dirty_id)
        if doc and doc.frontmatter.get("status") in {"approved", "done"}:
            update_artifact_frontmatter(
                repository_root / doc.path, {"status": "needs_update"}
            )


def resolve_escalation(
    repository_root: Path, escalation_id: str, resolved_by: str
) -> list[Finding]:
    """Resolve an Escalation with a Decision or Task and propagate dirty flags."""
    by_identifier = load_artifacts_by_id(repository_root)
    escalation = by_identifier.get(escalation_id)
    resolution = by_identifier.get(resolved_by)
    if escalation is None or escalation.artifact_type != "ESC":
        message = f"Escalation '{escalation_id}' not found."
        return [Finding(escalation_id, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    if resolution is None or resolution.artifact_type not in {"DEC", "TASK"}:
        message = f"Resolving Decision or Task '{resolved_by}' not found."
        return [Finding(resolved_by, 1, "CLI_ARTIFACT_NOT_FOUND", message)]
    errors = check_transition(repository_root, escalation, "resolved")
    if (
        resolution.artifact_type == "DEC"
        and resolution.frontmatter.get("status") != "approved"
    ):
        errors.extend(check_transition(repository_root, resolution, "approved"))
    if errors:
        return errors
    findings = run_checks(
        repository_root,
        ["glossary", "schemas", "traceability"],
        target_paths=[resolution.path],
    )
    if findings:
        return findings
    if resolution.artifact_type == "DEC":
        update_artifact_frontmatter(
            repository_root / resolution.path, {"status": "approved"}
        )
    update_artifact_frontmatter(
        repository_root / escalation.path,
        {"status": "resolved", "resolved_by": resolved_by},
    )
    _mark_dirty_subgraph(repository_root, by_identifier, resolved_by)
    return []


def finalize_stage_escalation(
    repository_root: Path,
    worktree_path: Path,
    target_id: str,
    escalation_path: str,
) -> tuple[list[str], list[Finding]]:
    """Merge a stage Escalation onto BaseBranch, route it, and block target_id."""
    merge_worktree_files(repository_root, worktree_path, [escalation_path])
    route = route_escalation(repository_root, escalation_path)
    update_artifact_frontmatter(
        repository_root / escalation_path, {"status": route.next_status}
    )
    target_doc = load_artifacts_by_id(repository_root).get(target_id)
    changed = [escalation_path]
    if target_doc is not None and target_doc.artifact_type in {"REQ", "SPEC", "TASK"}:
        update_artifact_frontmatter(
            repository_root / target_doc.path, {"status": "blocked"}
        )
        changed.append(target_doc.path)
    subject = (
        f"{route.escalation_id}: Escalate {target_id} to "
        f"{route.target_actor} ({route.action}) "
        f"[traces: {target_id}, {route.escalation_id}]"
    )
    commit_traceable_change(repository_root, changed, subject)
    message = (
        f"Stage '{target_id}' escalated to '{route.target_actor}' ({route.action})."
    )
    return [], [Finding(escalation_path, 1, "GATE_TASK_ESCALATED", message)]


def dispatch_routed_escalation(
    repository_root: Path,
    pipeline: dict[str, Any],
    options: tuple[str | None, str | None, str | None],
    stage_executor: Any,
) -> tuple[list[str], list[Finding]] | None:
    """Dispatch the first routed_to_agent Escalation via stage_executor."""
    for esc_id, document in sorted(load_artifacts_by_id(repository_root).items()):
        if (
            document.artifact_type != "ESC"
            or document.frontmatter.get("status") != "routed_to_agent"
        ):
            continue
        category = str(document.frontmatter.get("reason_category", "ambiguity"))
        routes: dict[str, Any] = pipeline.get("escalation_routes", {})
        actor = str(routes.get(category, {}).get("target_actor", "human"))
        if actor == "human":
            update_artifact_frontmatter(
                repository_root / document.path, {"status": "awaiting_human"}
            )
            commit_traceable_change(
                repository_root,
                [document.path],
                f"{esc_id}: Route escalation to human [traces: {esc_id}]",
            )
            return None
        produced, findings = stage_executor(repository_root, actor, esc_id, options)
        next_state = "awaiting_human" if findings else "resolved"
        resolved_by = (
            produced[0]
            if not findings and produced and produced[0].startswith(("DEC-", "TASK-"))
            else None
        )
        update_artifact_frontmatter(
            repository_root / document.path,
            {"status": next_state, "resolved_by": resolved_by},
        )
        commit_traceable_change(
            repository_root,
            [document.path],
            f"{esc_id}: Resolve escalation via {actor} [traces: {esc_id}]",
        )
        return [esc_id, *produced], findings
    return None


def reset_rejected_stage_artifacts(repository_root: Path, produced: list[str]) -> None:
    """Reset review-rejected REQ/SPEC to draft and TASK to blocked on BaseBranch."""
    by_id = load_artifacts_by_id(repository_root)
    changed: list[str] = []
    for artifact_id in produced:
        doc = by_id.get(artifact_id)
        if doc and doc.artifact_type in {"REQ", "SPEC", "TASK"}:
            reset_state = "blocked" if doc.artifact_type == "TASK" else "draft"
            update_artifact_frontmatter(
                repository_root / doc.path, {"status": reset_state}
            )
            changed.append(doc.path)
    if changed and produced:
        subject = (
            f"{produced[0]}: Reset rejected stage artifact "
            f"[traces: {', '.join(produced)}]"
        )
        commit_traceable_change(repository_root, changed, subject)


def handle_pipeline_step_outcome(
    repository_root: Path, produced: list[str], findings: list[Finding]
) -> tuple[list[str], list[Finding], bool]:
    """Handle review rejections and auto-routed escalations between pipeline steps."""
    if not findings:
        return produced, [], bool(produced)
    rule_ids = {item.rule_id for item in findings}
    if rule_ids == {"STAGE_REVIEW_REJECTED"}:
        reset_rejected_stage_artifacts(repository_root, produced)
        return [], [], True
    if rule_ids == {"GATE_TASK_ESCALATED"}:
        routed_ids = [
            str(doc.frontmatter["id"])
            for item in findings
            if (doc := parse_artifact_file(repository_root / item.path, item.path)[0])
            is not None
            and doc.frontmatter.get("status") == "routed_to_agent"
        ]
        if routed_ids and len(routed_ids) == len(findings):
            return [*produced, *routed_ids], [], True
    return produced, findings, False
