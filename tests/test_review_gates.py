"""TestContracts for stage review gates, REV traceability, and multi-REQ review."""

import importlib
from pathlib import Path
from typing import Any

import yaml

from multi_tasker.checkers.traceability_checker import check_traceability
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file, parse_artifact_file
from multi_tasker.orchestrator.stage_runner import run_agent_stage
from tests.test_interaction_logging import _seed_test_repository
from tests.test_stage_runner import (
    _GIT_PIPELINE_SCRIPT,
    _seed_approved_requirement,
    _seed_pipeline_escalation_fixture,
)


def _configure_single_cycle_review_pipeline(tmp_path: Path) -> None:
    """Disable target_files task coverage check and set max_review_cycles to 1."""
    trace_path = tmp_path / "policy" / "traceability.yaml"
    trace_policy = load_yaml_file(trace_path)
    trace_policy["traceability_rules"]["require_spec_target_files_covered_by_tasks"] = (
        False
    )
    trace_path.write_text(yaml.safe_dump(trace_policy), encoding="utf-8")
    pipeline_path = tmp_path / "policy" / "pipeline.yaml"
    pipeline = load_yaml_file(pipeline_path)
    assert pipeline["stages"][1]["approval_gate"] == "review-agent"
    assert pipeline["stages"][2]["approval_gate"] == "review-agent"
    pipeline["execution_bounds"]["max_review_cycles"] = 1
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")


@traces("REQ-015", "AC-01", "SPEC-015")
def test_pipeline_review_gate_verdict_and_exhaustion_escalation(
    tmp_path: Path, capsys: Any
) -> None:
    """Verify review-agent gate approves on pass and escalates on fail exhaustion."""
    _seed_test_repository(tmp_path)
    agent_cmd = _seed_pipeline_escalation_fixture(tmp_path)
    _configure_single_cycle_review_pipeline(tmp_path)
    run_args = [
        "run",
        "--pipeline",
        "--agent-command",
        agent_cmd,
        "--root",
        str(tmp_path),
    ]
    assert main(run_args) == 0
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(run_args) == 1
    assert "[STAGE_REVIEW_EXHAUSTED]" in capsys.readouterr().out
    spec_doc, _ = parse_artifact_file(
        tmp_path / "artifacts" / "specifications" / "SPEC-001.md",
        "artifacts/specifications/SPEC-001.md",
    )
    esc_doc, _ = parse_artifact_file(
        tmp_path / "artifacts" / "escalations" / "ESC-001.md",
        "artifacts/escalations/ESC-001.md",
    )
    assert spec_doc is not None and spec_doc.frontmatter["status"] == "approved"
    assert esc_doc is not None
    assert esc_doc.frontmatter["reason_category"] == "review_exhausted"
    assert esc_doc.frontmatter["status"] == "awaiting_human"


@traces("REQ-015", "AC-02", "SPEC-015")
def test_review_record_traceability_documentation_and_stage_gate_log(
    tmp_path: Path,
) -> None:
    """Verify REV target_artifacts traceability, Mermaid edges, and merge_gate logs."""
    _seed_test_repository(tmp_path)
    _seed_approved_requirement(tmp_path)
    rev_cmd = (
        'python3 -c "from pathlib import Path; '
        "Path('artifacts/reviews/REV-001.md').write_text("
        "'---\\nid: REV-001\\ntarget_artifacts: [REQ-001]\\n"
        "stage: requirement\\nverdict: pass\\nfindings: []\\n---\\nPassed.\\n')\""
    )
    produced, findings = run_agent_stage(
        tmp_path, "review-agent", "REQ-001", (rev_cmd, None, None)
    )
    assert findings == [] and produced == ["REV-001"]
    log_text = (tmp_path / ".report" / "logs" / "tasks" / "REQ-001.jsonl").read_text(
        encoding="utf-8"
    )
    assert '"agent_invocation"' in log_text and '"merge_gate"' in log_text
    spec_report = (tmp_path / ".report" / "specification.md").read_text(
        encoding="utf-8"
    )
    assert 'REV_001["REV-001: requirement (pass)"]' in spec_report
    assert "REQ_001 -.-> REV_001" in spec_report
    (tmp_path / "artifacts" / "reviews" / "REV-002.md").write_text(
        "---\nid: REV-002\ntarget_artifacts: [REQ-999]\n"
        "stage: requirement\nverdict: fail\nfindings: []\n---\nMissing ref.\n",
        encoding="utf-8",
    )
    trace_findings = check_traceability(tmp_path)
    assert any(item.rule_id == "TRACE_MISSING_REF" for item in trace_findings)


def _seed_real_git_pipeline_repo(tmp_path: Path) -> str:
    """Bootstrap a committed real-Git repo with auto INT gate and 2-task planner."""
    lifecycle = importlib.import_module("multi_tasker.orchestrator.lifecycle")
    lifecycle.bootstrap_evaluation_repository(tmp_path, "Add calculation helper.")
    script_path = tmp_path / ".report" / "real_git_agent.py"
    script_path.write_text(_GIT_PIPELINE_SCRIPT, encoding="utf-8")
    return f"python3 {script_path}"


@traces("REQ-021", "AC-01", "SPEC-021")
@traces("REQ-021", "AC-02", "SPEC-021")
@traces("REQ-027", "AC-01", "SPEC-027")
def test_real_git_pipeline_commits_verification_pythonpath_and_rev_traceability(
    tmp_path: Path, capsys: Any
) -> None:
    """Verify full E2E pipeline in a real Git repo passes MergeGate and check all."""
    from multi_tasker.orchestrator.prompt_builder import resolve_task_execution

    agent_cmd = _seed_real_git_pipeline_repo(tmp_path)
    intent_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/intents/INT-001.md", "artifacts/intents/INT-001.md"
    )
    assert intent_doc is not None
    default_resolved = resolve_task_execution(tmp_path, intent_doc)
    assert default_resolved[0] is not None and "agy" in default_resolved[0]
    capsys.readouterr()
    run_args = ["run", "--pipeline", "--agent-command", agent_cmd, "--root"]
    assert main([*run_args, str(tmp_path)]) == 0
    completed = capsys.readouterr().out.strip().splitlines()
    for expected_id in ("REQ-001", "SPEC-001", "REV-SPEC-001", "TASK-001", "TASK-002"):
        assert expected_id in completed
    assert main(["check", "all", "--root", str(tmp_path)]) == 0


_MULTI_REQ_STAGE_SCRIPT = (
    "import os\nfrom pathlib import Path\n"
    "role, target = os.environ['MT_AGENT_ROLE'], os.environ.get('MT_TASK_ID', '')\n"
    "fail_second = os.environ.get('FAIL_SECOND_REV') == '1'\n"
    "if role == 'requirement-agent':\n"
    "    for rid in ('REQ-001', 'REQ-002'):\n"
    "        Path(f'artifacts/requirements/{rid}.md').write_text("
    "f'---\\nid: {rid}\\ntitle: Atomic {rid}\\nstatus: in_review\\n"
    "traces_to: [INT-001]\\ndecisions: []\\nacceptance_criteria:\\n"
    "  - id: AC-01\\n    given: valid\\n    when: run\\n    then: done\\n"
    "version: 1\\n---\\n## Statement\\nStmt.\\n\\n## Impact Analysis\\nImp.\\n')\n"
    "elif role == 'review-agent':\n"
    "    v = 'fail' if (fail_second and target == 'REQ-002') else 'pass'\n"
    "    Path(f'artifacts/reviews/REV-{target}.md').write_text("
    "f'---\\nid: REV-{target}\\ntarget_artifacts: [{target}]\\n"
    "stage: requirement\\nverdict: {v}\\nfindings: []\\n---\\nReview.\\n')\n"
)


@traces("REQ-037", "AC-01", "SPEC-037")
@traces("REQ-037", "AC-03", "SPEC-037")
def test_multi_artifact_stage_review_pass_and_second_artifact_rejection(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Verify _step_declarative_stage reviews all artifacts and halts on rejection."""
    from multi_tasker.orchestrator.stage_runner import _step_declarative_stage

    _seed_test_repository(tmp_path)
    assert main(["intent", "Two capabilities.", "--root", str(tmp_path)]) == 0
    script_path = tmp_path / "multi_req_agent.py"
    script_path.write_text(_MULTI_REQ_STAGE_SCRIPT, encoding="utf-8")
    stage = {"agent_role": "requirement-agent", "approval_gate": "review-agent"}
    options = (f"python3 {script_path}", None, None)
    monkeypatch.setenv("FAIL_SECOND_REV", "1")
    produced, findings = _step_declarative_stage(tmp_path, stage, "INT-001", options)
    assert any(item.rule_id == "STAGE_REVIEW_REJECTED" for item in findings)
    assert "REV-REQ-001" in produced
    req2_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/requirements/REQ-002.md",
        "artifacts/requirements/REQ-002.md",
    )
    assert req2_doc and req2_doc.frontmatter["status"] == "in_review"
    for path in (tmp_path / "artifacts/reviews").glob("*.md"):
        path.unlink()
    for path in (tmp_path / "artifacts/requirements").glob("*.md"):
        path.unlink()
    monkeypatch.setenv("FAIL_SECOND_REV", "0")
    produced_ok, findings_ok = _step_declarative_stage(
        tmp_path, stage, "INT-001", options
    )
    assert findings_ok == []
    assert {"REQ-001", "REQ-002", "REV-REQ-001", "REV-REQ-002"} <= set(produced_ok)
    intent_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/intents/INT-001.md", "artifacts/intents/INT-001.md"
    )
    assert intent_doc and intent_doc.frontmatter["status"] == "processed"
