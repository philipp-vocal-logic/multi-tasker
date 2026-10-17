"""Deterministic tiered Escalation router driven by policy/pipeline.yaml."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.parser import (
    load_artifacts_by_id,
    load_pipeline_policy,
    parse_artifact_file,
)
from src.orchestrator.scheduler import select_parallel_batch


@dataclass(frozen=True)
class RouteDecision:
    """Deterministic routing outcome for an Escalation artifact."""

    escalation_id: str
    target_actor: str
    next_status: str
    action: str


CATEGORY_ROUTES: dict[str, tuple[str, str, str]] = {
    "infeasible_scope": ("planner-agent", "routed_to_agent", "rescope_task"),
    "test_contract_defect": (
        "review-agent",
        "routed_to_agent",
        "verify_test_contract",
    ),
    "ambiguity": ("human", "awaiting_human", "require_decision"),
    "rule_conflict": ("human", "awaiting_human", "require_decision"),
    "review_exhausted": ("human", "awaiting_human", "require_decision"),
}


def _load_routing_table(
    repository_root: Path,
) -> tuple[dict[str, tuple[str, str, str]], int]:
    """Load escalation_routes and max_auto_reroutes from policy/pipeline.yaml."""
    pipeline = load_pipeline_policy(repository_root)
    bounds: dict[str, Any] = pipeline.get("execution_bounds", {})
    max_reroutes = int(bounds.get("max_auto_reroutes", 1))
    raw_routes: dict[str, Any] = pipeline.get("escalation_routes", {})
    if not raw_routes:
        return dict(CATEGORY_ROUTES), max_reroutes
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
    covered = {
        str(upstream)
        for doc in by_id.values()
        if doc.artifact_type == downstream_type
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
