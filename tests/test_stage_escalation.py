"""TestContracts for lifecycle decomposition, stage escalation, and pipeline."""

import importlib
from pathlib import Path

import pytest

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
        "## Blocking Problem\\nRequire clarification on intent scope.\\n')\""
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


@traces("REQ-043", "AC-01", "SPEC-043")
@traces("REQ-043", "AC-02", "SPEC-043")
@traces("REQ-043", "AC-03", "SPEC-043")
@traces("REQ-049", "AC-03", "SPEC-049")
def test_declarative_pipeline_max_workers_forwarding_and_failure_halt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify mt run --pipeline forwards max_workers, defaults to 1, and halts."""
    from multi_tasker.cli.main import main
    from multi_tasker.domain.models import Finding
    from multi_tasker.orchestrator import stage_runner

    _seed_test_repository(tmp_path)
    for idx, mod_name in ((1, "src/a.py"), (2, "src/b.py")):
        (tmp_path / "artifacts" / "tasks" / f"TASK-00{idx}.md").write_text(
            f"---\nid: TASK-00{idx}\ntitle: Parallel Task {idx}\n"
            "type: implementation\nstatus: ready\ntraces_to: [SPEC-001]\n"
            f"depends_on: []\nrequired_files: []\nwrite_files: [{mod_name}]\n"
            "verification_cmd: pytest\n---\n"
            "## Objective\nObj.\n\n## Scoped Instructions\nInst.\n",
            encoding="utf-8",
        )
    recorded_workers: list[int] = []

    def fake_scheduled(
        repository_root: Path,
        max_workers: int = 1,
        agent_command: str | None = None,
        model_override: str | None = None,
        environment_override: str | None = None,
    ) -> tuple[list[str], list[Finding]]:
        _ = (repository_root, agent_command, model_override, environment_override)
        recorded_workers.append(max_workers)
        if max_workers == 3:
            return [], [Finding("verification_cmd", 1, "GATE_VERIFY_CMD_FAILED", "err")]
        return ["TASK-001", "TASK-002"], []

    monkeypatch.setattr(stage_runner, "run_scheduled_tasks", fake_scheduled)
    done_default, err_default = stage_runner.run_declarative_pipeline(tmp_path)
    assert {"TASK-001", "TASK-002"} <= set(done_default) and err_default == []
    assert recorded_workers[-1] == 1
    run_two = ["run", "--pipeline", "--max-workers", "2", "--root", str(tmp_path)]
    assert main(run_two) == 0 and recorded_workers[-1] == 2
    run_three = ["run", "--pipeline", "--max-workers", "3", "--root", str(tmp_path)]
    assert main(run_three) == 1 and recorded_workers[-1] == 3


@traces("REQ-044", "AC-01", "SPEC-044")
@traces("REQ-044", "AC-02", "SPEC-044")
@traces("REQ-044", "AC-03", "SPEC-044")
def test_legacy_context_mode_deprecation_and_documentation_alignment(
    tmp_path: Path,
) -> None:
    """Verify REQ-012/SPEC-012 deprecation and removal of context-mode from docs."""
    from multi_tasker.checkers.traceability_checker import check_traceability
    from multi_tasker.orchestrator.documentation_generator import (
        generate_external_agents_guide,
    )
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt

    checkout_root = Path(__file__).resolve().parent.parent
    for rel_path in (
        "artifacts/requirements/REQ-012.md",
        "artifacts/specifications/SPEC-012.md",
    ):
        doc, _ = parse_artifact_file(checkout_root / rel_path, rel_path)
        assert doc is not None and doc.frontmatter["status"] == "deprecated"
    prompt_text, _ = build_agent_prompt(checkout_root, "requirement-agent", "INT-043")
    assert "`REQ-012`:" not in prompt_text
    readme_text = (checkout_root / "README.md").read_text(encoding="utf-8")
    guide_text = generate_external_agents_guide()
    for text in (readme_text, guide_text):
        assert "default_context_mode" not in text
        assert "--context-mode" not in text
        assert "mt prompt <agent-role> [--target <id>]" in text
    _seed_test_repository(tmp_path)
    (tmp_path / "artifacts/requirements/REQ-012.md").write_text(
        "---\nid: REQ-012\ntitle: Legacy Context Mode\nstatus: deprecated\n"
        "traces_to: [INT-001]\ndecisions: []\n"
        "acceptance_criteria: [{id: AC-01, given: a, when: b, then: c}]\n"
        "version: 1\n---\n## Statement\nOld.\n\n## Impact Analysis\nOld.\n",
        encoding="utf-8",
    )
    (tmp_path / "artifacts/specifications/SPEC-099.md").write_text(
        "---\nid: SPEC-099\ntitle: Active Spec Referencing Deprecated Req\n"
        "status: draft\ntraces_to: [REQ-012]\ncovers_criteria: [REQ-012:AC-01]\n"
        "decisions: []\n"
        "target_files: {tests: [tests/t.py], implementation: [src/a.py]}\n---\n",
        encoding="utf-8",
    )
    findings = check_traceability(tmp_path, ["artifacts/specifications/SPEC-099.md"])
    assert any(item.rule_id == "TRACE_UPSTREAM_NOT_APPROVED" for item in findings)
