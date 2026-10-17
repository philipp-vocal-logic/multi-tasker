"""Executable TestContracts for REQ-013 and SPEC-013 per-agent Worktree & models."""

import importlib
from pathlib import Path
from typing import Any

import yaml

from src.checkers.permissions_checker import check_permissions
from src.cli.main import main
from src.domain.models import traces
from src.domain.parser import load_yaml_file, parse_artifact_file
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
