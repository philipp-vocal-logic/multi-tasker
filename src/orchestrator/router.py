"""Deterministic tiered Escalation router."""

from dataclasses import dataclass
from pathlib import Path

from src.domain.parser import load_artifacts_by_id, parse_artifact_file


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
    """Route an Escalation by reason_category with max 1 auto-reroute."""
    absolute_path = repository_root / escalation_relative_path
    document, findings = parse_artifact_file(absolute_path, escalation_relative_path)
    if findings or document is None:
        return RouteDecision("UNKNOWN", "human", "awaiting_human", "invalid_escalation")
    escalation_id = str(document.frontmatter.get("id", "UNKNOWN"))
    category = str(document.frontmatter.get("reason_category", "ambiguity"))
    task_or_stage = str(document.frontmatter.get("task_or_stage", ""))
    effective_reroutes = max(
        prior_reroutes,
        _count_prior_reroutes(repository_root, escalation_id, task_or_stage),
    )
    if effective_reroutes >= 1:
        return RouteDecision(
            escalation_id, "human", "awaiting_human", "reroute_limit_reached"
        )
    actor, status, action = CATEGORY_ROUTES.get(
        category, ("human", "awaiting_human", "require_decision")
    )
    return RouteDecision(escalation_id, actor, status, action)
