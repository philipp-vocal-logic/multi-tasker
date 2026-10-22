"""TestContracts for documentation_generator, lineage, and supersession."""

from pathlib import Path

import pytest

from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import parse_artifact_file
from tests.test_lifecycle import _seed_policies, _write_document


@traces("REQ-006", "AC-01", "SPEC-006")
@traces("REQ-006", "AC-02", "SPEC-006")
def test_continual_report_documentation_generation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify .report/specification.md updates across lifecycle and CLI."""
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    report_file = tmp_path / ".report" / "specification.md"
    gitignore_file = tmp_path / ".report" / ".gitignore"
    assert report_file.is_file() and gitignore_file.read_text("utf-8").strip() == "*"
    assert main(["intent", "Track report updates.", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert "INT-001" in report_file.read_text("utf-8")
    assert main(["documentation", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == report_file.read_text("utf-8")


def _seed_spec_report_fixture(tmp_path: Path) -> None:
    """Seed Intents, orphan Requirement, and sample module/test for report checks."""
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    assert main(["intent", "First intent.", "--root", str(tmp_path)]) == 0
    assert main(["intent", "Second intent.", "--root", str(tmp_path)]) == 0
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\ntitle: Req One\nstatus: approved\n"
        "traces_to: [INT-001]\nacceptance_criteria: [{id: AC-01}]\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/requirements/REQ-099.md",
        "---\nid: REQ-099\ntitle: Orphan Req\nstatus: draft\ntraces_to: []\n---\n",
    )
    _write_document(
        tmp_path / "src/sample_mod.py",
        "def compute_sum(left: int, right: int) -> int:\n    return left + right\n",
    )
    _write_document(
        tmp_path / "tests/test_sample_mod.py",
        "from multi_tasker.domain.models import traces\n"
        "from sample_mod import compute_sum\n\n"
        '@traces("REQ-001", "AC-01", "SPEC-001")\n'
        "def test_compute_sum() -> None:\n"
        "    assert compute_sum(2, 3) == 5\n",
    )


@traces("REQ-032", "AC-01", "SPEC-032")
@traces("REQ-032", "AC-02", "SPEC-032")
@traces("REQ-032", "AC-03", "SPEC-032")
def test_specification_report_intent_graphs_pipeline_prompts_and_coverage(
    tmp_path: Path,
) -> None:
    """Verify per-Intent graphs, pipeline diagram, example prompts, and coverage."""
    from multi_tasker.orchestrator.documentation_generator import (
        write_repository_documentation,
    )
    from multi_tasker.orchestrator.lineage import collect_pytest_line_coverage

    _seed_spec_report_fixture(tmp_path)
    cov_data = collect_pytest_line_coverage(tmp_path)
    assert cov_data["exit_code"] == 0 and cov_data["covered_lines"] >= 2
    report_text = write_repository_documentation(tmp_path).read_text(encoding="utf-8")
    for expected in (
        "### INT-001",
        "### INT-002",
        "### Unlinked Artifacts",
        "## 6. Declarative Agent Pipeline & Escalation Routing",
        "intent_to_requirement",
        "infeasible_scope",
        "## 7. Generated Example Agent Instructions",
        "<details>",
        "````markdown",
        "# Role Prompt: `worker-agent`",
        "## 8. Test & Code Coverage Report",
        "`src/sample_mod.py`",
        "100.0%",
    ):
        assert expected in report_text
    assert "### Verified TestContract Links" not in report_text


def _seed_supersession_fixture(tmp_path: Path) -> Path:
    """Seed INT-001..002, REQ-001, SPEC-001, TASK-001, and draft REQ-002."""
    _seed_policies(tmp_path)
    for intent_id, state_val in (("INT-001", "processed"), ("INT-002", "open")):
        _write_document(
            tmp_path / f"artifacts/intents/{intent_id}.md",
            f"---\nid: {intent_id}\nstatus: {state_val}\n---\n",
        )
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\ntitle: Legacy Auth\nstatus: approved\n"
        "traces_to: [INT-001]\nacceptance_criteria: [{id: AC-01}]\n"
        "version: 1\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01]\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nstatus: done\ntraces_to: [REQ-001, SPEC-001]\n---\n",
    )
    req2_path = tmp_path / "artifacts/requirements/REQ-002.md"
    _write_document(
        req2_path,
        "---\nid: REQ-002\ntitle: Modern Auth\nstatus: draft\n"
        "traces_to: [INT-002]\nsupersedes: [REQ-999]\n"
        "acceptance_criteria: [{id: AC-01}]\n---\n",
    )
    return req2_path


@traces("REQ-039", "AC-01", "SPEC-039")
@traces("REQ-039", "AC-02", "SPEC-039")
@traces("REQ-039", "AC-03", "SPEC-039")
def test_requirement_supersession_deprecates_old_req_and_spec(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify supersedes auto-deprecates REQ/SPEC and filters trace/prompt/metrics."""
    from multi_tasker.checkers.traceability_checker import check_traceability
    from multi_tasker.orchestrator.lineage import _compute_static_test_metrics
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt

    req2_path = _seed_supersession_fixture(tmp_path)
    assert main(["approve", "REQ-002", "--root", str(tmp_path)]) == 1
    assert "[TRACE_MISSING_REF]" in capsys.readouterr().out
    _write_document(
        req2_path, req2_path.read_text("utf-8").replace("REQ-999", "REQ-001")
    )
    assert main(["approve", "REQ-002", "--root", str(tmp_path)]) == 0
    for rel_path in ("requirements/REQ-001.md", "specifications/SPEC-001.md"):
        doc, _ = parse_artifact_file(tmp_path / "artifacts" / rel_path, rel_path)
        assert doc and doc.frontmatter["status"] == "deprecated"
    assert check_traceability(tmp_path, ["artifacts/tasks/TASK-001.md"]) == []
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-002.md",
        "---\nid: SPEC-002\nstatus: draft\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-002:AC-01]\n---\n",
    )
    bad_refs = check_traceability(tmp_path, ["artifacts/specifications/SPEC-002.md"])
    assert any(item.rule_id == "TRACE_UPSTREAM_NOT_APPROVED" for item in bad_refs)
    prompt, _ = build_agent_prompt(tmp_path, "requirement-agent", "INT-002")
    assert "supersedes: [REQ-NNN]" in prompt
    assert "`REQ-002`: Modern Auth" in prompt
    assert "`REQ-001`: Legacy Auth" not in prompt
    assert _compute_static_test_metrics(tmp_path)[3] == "0/1 (0.0%)"


@traces("REQ-040", "AC-01", "SPEC-040")
@traces("REQ-040", "AC-02", "SPEC-040")
@traces("REQ-040", "AC-03", "SPEC-040")
def test_superseded_intent_subgraph_separation_and_inlined_spec_context(
    tmp_path: Path,
) -> None:
    """Verify disjoint Intent subgraphs, trace supersedes, and SPEC context."""
    from multi_tasker.domain.parser import load_artifacts_by_id
    from multi_tasker.orchestrator.lineage import (
        group_artifacts_by_intent,
        trace_lineage,
    )
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt

    req2_path = _seed_supersession_fixture(tmp_path)
    _write_document(tmp_path / "src/domain/auth.py", "AUTH_MOD = 1\n")
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01]\n"
        "target_files: {tests: [], implementation: [src/domain/auth.py]}\n---\n",
    )
    _write_document(
        req2_path, req2_path.read_text("utf-8").replace("REQ-999", "REQ-001")
    )
    assert main(["approve", "REQ-002", "--root", str(tmp_path)]) == 0
    groups = dict(group_artifacts_by_intent(load_artifacts_by_id(tmp_path)))
    assert "REQ-001" in groups["INT-001"] and "REQ-002" not in groups["INT-001"]
    assert "REQ-002" in groups["INT-002"] and "REQ-001" not in groups["INT-002"]
    assert any("REQ-002" in line for line in trace_lineage(tmp_path, "REQ-001"))
    spec_prompt, _ = build_agent_prompt(tmp_path, "specification-agent", "REQ-002")
    for expected in ("Artifact `REQ-001`", "Artifact `SPEC-001`", "AUTH_MOD = 1"):
        assert expected in spec_prompt
