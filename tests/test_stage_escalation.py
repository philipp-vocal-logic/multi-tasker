"""TestContracts for lifecycle decomposition, stage escalation, and pipeline."""

import importlib
from pathlib import Path

from multi_tasker.checkers.limits_checker import collect_refactoring_targets
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import parse_artifact_file
from tests.test_interaction_logging import _seed_test_repository


@traces("REQ-041", "AC-01", "SPEC-041")
@traces("REQ-041", "AC-02", "SPEC-041")
@traces("REQ-041", "AC-03", "SPEC-041")
def test_lifecycle_decomposition_and_router_cohesiveness(tmp_path: Path) -> None:
    """Verify zero src/ refactor hints and router ownership of escalation functions."""
    checkout_root = Path(__file__).resolve().parent.parent
    src_hints = [
        item
        for item in collect_refactoring_targets(checkout_root)
        if item.path.startswith("src/")
    ]
    assert src_hints == []
    lifecycle = importlib.import_module("multi_tasker.orchestrator.lifecycle")
    router = importlib.import_module("multi_tasker.orchestrator.router")
    for moved_name in ("evaluate_review_verdict", "resolve_escalation"):
        assert not hasattr(lifecycle, moved_name)
        assert callable(getattr(router, moved_name, None))
    _seed_test_repository(tmp_path)
    missing_esc = router.resolve_escalation(tmp_path, "ESC-404", "DEC-001")
    assert missing_esc[0].rule_id == "CLI_ARTIFACT_NOT_FOUND"
    esc_path = tmp_path / "artifacts" / "escalations" / "ESC-001.md"
    esc_path.write_text(
        "---\nid: ESC-001\nsource_agent: worker-agent\ntask_or_stage: TASK-001\n"
        "affected_artifacts: [TASK-001]\nreason_category: ambiguity\n"
        "status: awaiting_human\nresolved_by: null\n---\n"
        "## Blocking Problem\nClarify behavior.\n",
        encoding="utf-8",
    )
    missing_dec = router.resolve_escalation(tmp_path, "ESC-001", "DEC-404")
    assert missing_dec[0].rule_id == "CLI_ARTIFACT_NOT_FOUND"
    (tmp_path / "artifacts" / "tasks" / "TASK-001.md").write_text(
        "---\nid: TASK-001\ntitle: Sample Task\ntype: implementation\n"
        "status: blocked\ntraces_to: [SPEC-001]\ndepends_on: []\n"
        "required_files: []\nwrite_files: [src/a.py]\n"
        "verification_cmd: pytest\n---\n"
        "## Objective\nObj.\n\n## Scoped Instructions\nInst.\n",
        encoding="utf-8",
    )
    dec_path = tmp_path / "artifacts" / "decisions" / "DEC-001.md"
    dec_path.write_text(
        "---\nid: DEC-001\nresolves: ESC-001\napplies_to: [TASK-001]\n"
        "status: draft\n---\n## Resolution\nUse option A.\n",
        encoding="utf-8",
    )
    assert router.resolve_escalation(tmp_path, "ESC-001", "DEC-001") == []
    esc_doc, _ = parse_artifact_file(esc_path, "artifacts/escalations/ESC-001.md")
    assert esc_doc is not None and esc_doc.frontmatter["status"] == "resolved"


def _seed_stage_escalation_targets(tmp_path: Path) -> str:
    """Seed INT-001 and REQ-001 and return requirement-agent escalation command."""
    _seed_test_repository(tmp_path)
    (tmp_path / "artifacts" / "intents" / "INT-001.md").write_text(
        "---\nid: INT-001\nstatus: open\ncreated_at: '2026-10-22T00:00:00Z'\n---\n"
        "Ambiguous intent.\n",
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "requirements" / "REQ-001.md").write_text(
        "---\nid: REQ-001\ntitle: Approved Requirement\nstatus: approved\n"
        "traces_to: [INT-001]\ndecisions: []\n"
        "acceptance_criteria: [{id: AC-01, given: a, when: b, then: c}]\n"
        "version: 1\n---\n## Statement\nOk.\n\n## Impact Analysis\nOk.\n",
        encoding="utf-8",
    )
    return (
        'python3 -c "from pathlib import Path; '
        "Path('artifacts/escalations/ESC-001.md').write_text("
        "'---\\nid: ESC-001\\nsource_agent: requirement-agent\\n"
        "task_or_stage: INT-001\\naffected_artifacts: [INT-001]\\n"
        "reason_category: ambiguity\\nstatus: open\\nresolved_by: null\\n---\\n"
        "## Blocking Problem\\nNeed clarification on intent scope.\\n')\""
    )


@traces("REQ-042", "AC-01", "SPEC-042")
@traces("REQ-042", "AC-02", "SPEC-042")
@traces("REQ-042", "AC-03", "SPEC-042")
def test_stage_agent_escalation_persistence_routing_and_rejection(
    tmp_path: Path,
) -> None:
    """Verify run_agent_stage merges/routes valid ESC and rejects invalid ESC."""
    from multi_tasker.orchestrator.stage_runner import run_agent_stage

    esc_int_cmd = _seed_stage_escalation_targets(tmp_path)
    produced, findings = run_agent_stage(
        tmp_path, "requirement-agent", "INT-001", (esc_int_cmd, None, None)
    )
    assert produced == [] and findings[0].rule_id == "GATE_TASK_ESCALATED"
    esc_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/escalations/ESC-001.md", "ESC-001.md"
    )
    int_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/intents/INT-001.md", "INT-001.md"
    )
    assert esc_doc is not None and esc_doc.frontmatter["status"] == "awaiting_human"
    assert int_doc is not None and int_doc.frontmatter["status"] == "open"
    esc_req_cmd = esc_int_cmd.replace(
        "requirement-agent", "specification-agent"
    ).replace("INT-001", "REQ-001")
    _, req_findings = run_agent_stage(
        tmp_path, "specification-agent", "REQ-001", (esc_req_cmd, None, None)
    )
    assert req_findings[0].rule_id == "GATE_TASK_ESCALATED"
    req_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/requirements/REQ-001.md", "REQ-001.md"
    )
    assert req_doc is not None and req_doc.frontmatter["status"] == "blocked"
    bad_esc_cmd = (
        'python3 -c "from pathlib import Path; '
        "Path('artifacts/escalations/ESC-009.md').write_text('---\\nid: X\\n---\\n')\""
    )
    _, bad_findings = run_agent_stage(
        tmp_path, "requirement-agent", "INT-001", (bad_esc_cmd, None, None)
    )
    assert not (tmp_path / "artifacts/escalations/ESC-009.md").exists()
    assert any(item.rule_id != "GATE_TASK_ESCALATED" for item in bad_findings)
