"""Executable TestContracts for REQ-013/SPEC-013 and REQ-014/SPEC-014."""

import importlib
from pathlib import Path
from typing import Any

import yaml

from src.checkers.permissions_checker import check_permissions
from src.checkers.schemas_checker import check_schemas
from src.cli.main import main
from src.domain.models import traces
from src.domain.parser import load_yaml_file, parse_artifact_file
from src.orchestrator.router import route_escalation
from tests.test_interaction_logging import REPOSITORY_ROOT, _seed_test_repository


@traces("REQ-013", "AC-01", "SPEC-013")
def test_per_agent_model_precedence_and_policy_validation(tmp_path: Path) -> None:
    """Verify gemini-4-argon role defaults, 4-tier precedence, and policy checks."""
    _seed_test_repository(tmp_path)
    prompt_module = importlib.import_module("src.orchestrator.prompt_builder")
    intent_path = tmp_path / "artifacts" / "intents" / "INT-001.md"
    intent_path.write_text(
        "---\nid: INT-001\nstatus: open\ncreated_at: '2026-10-17T00:00:00Z'\n---\n"
        "Support stage orchestration.\n",
        encoding="utf-8",
    )
    intent_doc, _ = parse_artifact_file(intent_path, "artifacts/intents/INT-001.md")
    assert intent_doc is not None
    for high_role in (
        "requirement-agent",
        "specification-agent",
        "planner-agent",
        "review-agent",
    ):
        resolved = prompt_module.resolve_task_execution(
            tmp_path, intent_doc, (None, None, None), high_role
        )
        assert resolved[2] == "gemini-4-argon"
    worker_resolved = prompt_module.resolve_task_execution(
        tmp_path, intent_doc, (None, None, None), "worker-agent"
    )
    assert worker_resolved[2] == "gemini-3.8-flash-high"
    cli_override = prompt_module.resolve_task_execution(
        tmp_path, intent_doc, (None, "custom-cli-model", None), "planner-agent"
    )
    assert cli_override[2] == "custom-cli-model"
    permissions_path = tmp_path / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path)
    permissions["agents"]["planner-agent"]["worktree_execution"] = "not-a-bool"
    permissions_path.write_text(yaml.safe_dump(permissions), encoding="utf-8")
    findings = check_permissions(tmp_path)
    assert any(item.rule_id == "PERM_INVALID_EXEC_ENV" for item in findings)


def _seed_approved_requirement(tmp_path: Path) -> None:
    """Seed INT-001 and approved REQ-001 in tmp_path."""
    (tmp_path / "artifacts" / "intents" / "INT-001.md").write_text(
        "---\nid: INT-001\nstatus: processed\ncreated_at: '2026-10-17T00:00:00Z'\n"
        "---\nAdd configurable stage runner.\n",
        encoding="utf-8",
    )
    (tmp_path / "artifacts" / "requirements" / "REQ-001.md").write_text(
        "---\nid: REQ-001\ntitle: Configurable Stage Runner Requirement\n"
        "status: approved\ntraces_to:\n  - INT-001\ndecisions: []\n"
        "acceptance_criteria:\n  - id: AC-01\n    given: An approved Requirement\n"
        "    when: specification-agent runs\n    then: Produces SPEC-001\n"
        "version: 1\n---\n## Statement\nRun stage agents in Worktrees.\n\n"
        "## Impact Analysis\nAdds stage runner.\n",
        encoding="utf-8",
    )


@traces("REQ-013", "AC-02", "SPEC-013")
def test_configurable_worktree_stage_execution_and_toggle(
    tmp_path: Path, capsys: Any
) -> None:
    """Verify mt run --agent executes in Worktree with gemini-4-argon and toggle."""
    _seed_test_repository(tmp_path)
    _seed_approved_requirement(tmp_path)
    specification_command = (
        'python3 -c "import os; from pathlib import Path; '
        "assert os.environ['MT_AGENT_ROLE'] == 'specification-agent'; "
        "assert os.environ['MT_AGENT_MODEL'] == 'gemini-4-argon'; "
        "Path('artifacts/specifications/SPEC-001.md').write_text("
        "'---\\nid: SPEC-001\\ntitle: Stage Runner Specification\\n"
        "status: draft\\ntraces_to: [REQ-001]\\ncovers_criteria: [REQ-001:AC-01]\\n"
        "decisions: []\\ntarget_files:\\n  tests: [tests/test_x.py]\\n"
        "  implementation: [src/domain/x.py]\\n---\\n"
        "## Design Overview\\nDesign.\\n\\n## Public Interfaces\\nNone.\\n\\n"
        "## Test Contract Mapping\\n- REQ-001:AC-01 -> test_x\\n')\""
    )
    run_args = [
        "run",
        "--agent",
        "specification-agent",
        "--target",
        "REQ-001",
        "--agent-command",
        specification_command,
        "--root",
        str(tmp_path),
    ]
    assert main(run_args) == 0
    assert capsys.readouterr().out.strip() == "SPEC-001"
    assert (tmp_path / "artifacts" / "specifications" / "SPEC-001.md").is_file()
    permissions_path = tmp_path / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path)
    permissions["agents"]["specification-agent"]["worktree_execution"] = False
    permissions_path.write_text(yaml.safe_dump(permissions), encoding="utf-8")
    assert main(run_args) == 1
    assert "[CLI_AGENT_WORKTREE_DISABLED]" in capsys.readouterr().out
    assert REPOSITORY_ROOT.is_dir()


@traces("REQ-014", "AC-01", "SPEC-014")
def test_pipeline_policy_validation_and_configurable_escalation_routing(
    tmp_path: Path,
) -> None:
    """Verify check_schemas validates pipeline.yaml and router uses policy routes."""
    _seed_test_repository(tmp_path)
    assert check_schemas(tmp_path) == []
    pipeline_path = tmp_path / "policy" / "pipeline.yaml"
    pipeline = load_yaml_file(pipeline_path)
    pipeline["stages"][0]["approval_gate"] = "invalid-gate"
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    findings = check_schemas(tmp_path)
    assert any(item.rule_id == "PIPELINE_INVALID_STAGE" for item in findings)
    pipeline["stages"][0]["approval_gate"] = "human"
    pipeline["escalation_routes"]["ambiguity"] = {
        "target_actor": "requirement-agent",
        "next_status": "routed_to_agent",
        "action": "clarify_requirement",
    }
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    escalation_rel = "artifacts/escalations/ESC-001.md"
    (tmp_path / escalation_rel).write_text(
        "---\nid: ESC-001\nsource_agent: worker-agent\ntask_or_stage: TASK-001\n"
        "affected_artifacts: [REQ-001]\nreason_category: ambiguity\n"
        "status: open\n---\n## Blocking Problem\nAmbiguous requirement.\n",
        encoding="utf-8",
    )
    decision = route_escalation(tmp_path, escalation_rel)
    assert decision.target_actor == "requirement-agent"
    assert decision.next_status == "routed_to_agent"
    capped = route_escalation(tmp_path, escalation_rel, prior_reroutes=1)
    assert capped.target_actor == "human"
    assert capped.next_status == "awaiting_human"


def _seed_pipeline_escalation_fixture(tmp_path: Path) -> str:
    """Seed INT-001 and write a multi-stage agent dispatcher script in tmp_path."""
    assert main(["intent", "Goal.", "--root", str(tmp_path)]) == 0
    script_path = tmp_path / "pipeline_agent_helper.py"
    script_path.write_text(
        "import os\nfrom pathlib import Path\nrole = os.environ['MT_AGENT_ROLE']\n"
        "if role == 'requirement-agent':\n"
        "    Path('artifacts/requirements/REQ-001.md').write_text("
        "'---\\nid: REQ-001\\ntitle: Pipeline Requirement\\nstatus: draft\\n"
        "traces_to: [INT-001]\\ndecisions: []\\nacceptance_criteria:\\n"
        "  - id: AC-01\\n    given: Intent\\n    when: Run\\n    then: Done\\n"
        "version: 1\\n---\\n## Statement\\nStmt.\\n\\n## Impact Analysis\\nImp.\\n')\n"
        "elif role == 'specification-agent':\n"
        "    Path('artifacts/specifications/SPEC-001.md').write_text("
        "'---\\nid: SPEC-001\\ntitle: Pipeline Specification\\nstatus: draft\\n"
        "traces_to: [REQ-001]\\ncovers_criteria: [REQ-001:AC-01]\\ndecisions: []\\n"
        "target_files:\\n  tests: [tests/test_p.py]\\n"
        "  implementation: [src/domain/p.py]\\n"
        "---\\n## Design Overview\\nDesign.\\n\\n## Public Interfaces\\nPublic.\\n\\n"
        "## Test Contract Mapping\\n- REQ-001:AC-01 -> test_p\\n')\n"
        "elif role == 'planner-agent':\n"
        "    Path('artifacts/tasks/TASK-001.md').write_text("
        "'---\\nid: TASK-001\\ntitle: Rescoped Pipeline TestContract\\n"
        "type: test_contract\\nstatus: planned\\ntraces_to: [REQ-001, SPEC-001]\\n"
        "depends_on: []\\nrequired_files: []\\nwrite_files: [tests/test_p.py]\\n"
        "verification_cmd: python3 -c pass\\n---\\n"
        "## Objective\\nObj.\\n\\n## Scoped Instructions\\nInst.\\n')\n"
        "elif role == 'worker-agent':\n"
        "    Path('tests').mkdir(exist_ok=True)\n"
        "    Path('tests/test_p.py').write_text("
        "'from src.domain.models import traces\\n\\n"
        '@traces("REQ-001", "AC-01", "SPEC-001")\\n'
        "def test_p() -> None:\\n    assert True\\n')\n",
        encoding="utf-8",
    )
    return f"python3 {script_path}"


def _enable_auto_gates_and_seed_escalation(tmp_path: Path) -> None:
    """Switch pipeline approval_gate to auto, approve REQ-001, and seed ESC-001."""
    trace_path = tmp_path / "policy" / "traceability.yaml"
    trace_policy = load_yaml_file(trace_path)
    trace_policy["traceability_rules"]["require_spec_target_files_covered_by_tasks"] = (
        False
    )
    trace_path.write_text(yaml.safe_dump(trace_policy), encoding="utf-8")
    pipeline_path = tmp_path / "policy" / "pipeline.yaml"
    pipeline = load_yaml_file(pipeline_path)
    for stage in pipeline["stages"]:
        stage["approval_gate"] = "auto"
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    (tmp_path / "artifacts" / "escalations" / "ESC-001.md").write_text(
        "---\nid: ESC-001\nsource_agent: worker-agent\ntask_or_stage: TASK-001\n"
        "affected_artifacts: [REQ-001]\nreason_category: infeasible_scope\n"
        "status: routed_to_agent\n---\n## Blocking Problem\nNeeds rescope.\n",
        encoding="utf-8",
    )


@traces("REQ-014", "AC-02", "SPEC-014")
def test_declarative_pipeline_execution_gates_and_auto_escalation(
    tmp_path: Path, capsys: Any
) -> None:
    """Verify mt run --pipeline pauses on human gate and self-heals escalations."""
    _seed_test_repository(tmp_path)
    agent_cmd = _seed_pipeline_escalation_fixture(tmp_path)
    capsys.readouterr()
    run_args = [
        "run",
        "--pipeline",
        "--agent-command",
        agent_cmd,
        "--root",
        str(tmp_path),
    ]
    assert main(run_args) == 0
    assert capsys.readouterr().out.strip() == "REQ-001"
    assert not (tmp_path / "artifacts" / "specifications" / "SPEC-001.md").exists()
    _enable_auto_gates_and_seed_escalation(tmp_path)
    assert main(run_args) == 0
    output_lines = capsys.readouterr().out.strip().splitlines()
    assert "SPEC-001" in output_lines and "TASK-001" in output_lines
    esc_doc, _ = parse_artifact_file(
        tmp_path / "artifacts" / "escalations" / "ESC-001.md",
        "artifacts/escalations/ESC-001.md",
    )
    task_doc, _ = parse_artifact_file(
        tmp_path / "artifacts" / "tasks" / "TASK-001.md",
        "artifacts/tasks/TASK-001.md",
    )
    assert esc_doc is not None and esc_doc.frontmatter["status"] == "resolved"
    assert task_doc is not None and task_doc.frontmatter["status"] == "done"
