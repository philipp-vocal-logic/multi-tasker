"""TestContracts for CLI lifecycle and documentation commands (`mt initialize`)."""

from pathlib import Path
import subprocess
from typing import Any

import pytest
import yaml

from src.checkers.common import get_git_changed_files
from src.checkers.permissions_checker import check_permissions
from src.cli.main import main
from src.domain.models import traces
from src.domain.parser import load_yaml_file, parse_artifact_file
from src.orchestrator.worktree import (
    create_worktree,
    remove_worktree,
    verify_clean_repository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _write_document(path: Path, text: str) -> None:
    """Create parent directories and write text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_policies(root: Path) -> None:
    """Write minimal valid policy/*.yaml files into root."""
    real_permissions = load_yaml_file(REPOSITORY_ROOT / "policy/permissions.yaml")
    real_schemas = load_yaml_file(REPOSITORY_ROOT / "policy/schemas.yaml")
    permissions: dict[str, Any] = {
        "clean_repo_invariants": {"require_empty_git_status_before_worktree": False},
        "global_forbidden_write": ["policy/**"],
        "agents": real_permissions.get("agents", {}),
    }
    traceability_rules = {
        "require_files_declared_in_spec_target_files": False,
        "require_spec_target_files_covered_by_tasks": False,
    }
    configurations: dict[str, dict[str, Any]] = {
        "permissions.yaml": permissions,
        "glossary.yaml": {"enforcement": {}, "terms": []},
        "limits.yaml": {"source_code": {}},
        "clean_code.yaml": {"linters": {"ruff": {"enabled": False}}, "ast_rules": {}},
        "architecture.yaml": {
            "dependency_rules": {},
            "layers": [{"name": "tests", "paths": ["tests/**"]}],
        },
        "schemas.yaml": {
            "state_transitions": real_schemas.get("state_transitions", {}),
            "artifacts": {},
            "schemas": {},
        },
        "traceability.yaml": {"traceability_rules": traceability_rules},
    }
    for name, data in configurations.items():
        _write_document(root / "policy" / name, yaml.safe_dump(data))


@traces("REQ-003", "AC-01", "SPEC-003")
def test_initialize_and_intent_creation_with_git(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt initialize`, `mt intent`, and Git worktree/status integration."""
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    assert (tmp_path / ".git").exists() and (tmp_path / "artifacts/intents").is_dir()
    assert main(["intent", "Support token revocation.", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "INT-001"
    message_file = tmp_path / "input.txt"
    message_file.write_text("Second raw Intent body.\n", encoding="utf-8")
    assert main(["intent", str(message_file), "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "INT-002"
    _seed_policies(tmp_path)
    for command in (
        ["git", "config", "user.email", "mt@example.com"],
        ["git", "config", "user.name", "mt"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", "initialize"],
    ):
        subprocess.run(command, cwd=tmp_path, check=True)
    worktree_path = create_worktree(tmp_path, "git-wt")
    _write_document(
        worktree_path / "artifacts/intents/INT-003.md", "---\nid: INT-003\n---\n"
    )
    assert "artifacts/intents/INT-003.md" in get_git_changed_files(worktree_path)
    assert verify_clean_repository(worktree_path)[0].rule_id == "GATE_DIRTY_REPO"
    remove_worktree(tmp_path, worktree_path)
    assert not worktree_path.exists()


@traces("REQ-003", "AC-02", "SPEC-003")
def test_approve_and_resolve_dirty_propagation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt approve` and `mt resolve` update status and mark downstream dirty."""
    _seed_policies(tmp_path)
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\nstatus: draft\n---\n## Statement\nOk.\n",
    )
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nstatus: done\ntraces_to: [SPEC-001]\n---\n",
    )
    assert main(["approve", "REQ-404", "--root", str(tmp_path)]) == 1
    assert "[CLI_ARTIFACT_NOT_FOUND]" in capsys.readouterr().out
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    specification, _ = parse_artifact_file(
        tmp_path / "artifacts/specifications/SPEC-001.md", "SPEC-001.md"
    )
    assert specification and specification.frontmatter["status"] == "needs_update"
    _write_document(
        tmp_path / "artifacts/escalations/ESC-001.md",
        "---\nid: ESC-001\nstatus: open\nresolved_by: null\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/decisions/DEC-001.md",
        "---\nid: DEC-001\nresolves: ESC-001\n"
        "applies_to: [REQ-001]\nstatus: draft\n---\n",
    )
    assert main(["resolve", "ESC-001", "--by", "DEC-001", "--root", str(tmp_path)]) == 0
    escalation, _ = parse_artifact_file(
        tmp_path / "artifacts/escalations/ESC-001.md", "ESC-001.md"
    )
    assert escalation and escalation.frontmatter["resolved_by"] == "DEC-001"


REQUIREMENT_PATH = "artifacts/requirements/REQ-001.md"
SPECIFICATION_PATH = "artifacts/specifications/SPEC-001.md"


@traces("REQ-001", "AC-01", "SPEC-001")
@traces("REQ-003", "AC-02", "SPEC-003")
@pytest.mark.parametrize(
    ("role", "relative_path", "transition", "expected_rule"),
    [
        ("requirement-agent", REQUIREMENT_PATH, ("needs_update", "draft"), None),
        (
            "requirement-agent",
            REQUIREMENT_PATH,
            ("needs_update", "in_review"),
            "PERM_INVALID_STATE_TRANSITION",
        ),
        (
            "requirement-agent",
            REQUIREMENT_PATH,
            ("draft", "approved"),
            "PERM_INVALID_TARGET_STATE",
        ),
        ("requirement-agent", REQUIREMENT_PATH, (None, "draft"), None),
        ("specification-agent", SPECIFICATION_PATH, ("needs_update", "draft"), None),
        (
            "specification-agent",
            SPECIFICATION_PATH,
            ("needs_update", "in_review"),
            "PERM_INVALID_STATE_TRANSITION",
        ),
        ("planner-agent", "artifacts/tasks/TASK-001.md", ("planned", "ready"), None),
        (
            "planner-agent",
            "artifacts/tasks/TASK-001.md",
            ("needs_update", "ready"),
            "PERM_INVALID_STATE_TRANSITION",
        ),
        (
            "planner-agent",
            "artifacts/tasks/TASK-001.md",
            ("planned", "done"),
            "PERM_INVALID_TARGET_STATE",
        ),
        ("worker-agent", "artifacts/escalations/ESC-001.md", (None, "open"), None),
        (
            "worker-agent",
            "artifacts/escalations/ESC-001.md",
            (None, "resolved"),
            "PERM_INVALID_TARGET_STATE",
        ),
    ],
)
def test_state_transitions_matrix(
    tmp_path: Path,
    role: str,
    relative_path: str,
    transition: tuple[str | None, str],
    expected_rule: str | None,
) -> None:
    """Verify valid and invalid state transitions across REQ, SPEC, TASK, and ESC."""
    old_state, new_state = transition
    _seed_policies(tmp_path)
    _write_document(
        tmp_path / relative_path, f"---\nid: ART-001\nstatus: {new_state}\n---\n"
    )
    states = {relative_path: old_state} if old_state is not None else {}
    findings = check_permissions(tmp_path, role, None, [relative_path], states)
    if expected_rule is None:
        assert findings == []
    else:
        assert any(finding.rule_id == expected_rule for finding in findings)


@traces("REQ-003", "AC-02", "SPEC-003")
def test_cli_approve_and_resolve_transition_guards(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt approve` and `mt resolve` reject invalid lifecycle transitions."""
    _seed_policies(tmp_path)
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\nstatus: deprecated\n---\n",
    )
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 1
    assert "[PERM_INVALID_STATE_TRANSITION]" in capsys.readouterr().out
    _write_document(
        tmp_path / "artifacts/escalations/ESC-001.md",
        "---\nid: ESC-001\nstatus: resolved\nresolved_by: DEC-001\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/decisions/DEC-001.md",
        "---\nid: DEC-001\nresolves: ESC-001\nstatus: approved\n---\n",
    )
    assert main(["resolve", "ESC-001", "--by", "DEC-001", "--root", str(tmp_path)]) == 1
    assert "[PERM_INVALID_STATE_TRANSITION]" in capsys.readouterr().out
    _write_document(
        tmp_path / "artifacts/escalations/ESC-001.md",
        "---\nid: ESC-001\nstatus: awaiting_human\nresolved_by: null\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/decisions/DEC-001.md",
        "---\nid: DEC-001\nresolves: ESC-001\nstatus: superseded\n---\n",
    )
    assert main(["resolve", "ESC-001", "--by", "DEC-001", "--root", str(tmp_path)]) == 1
    assert "[PERM_INVALID_STATE_TRANSITION]" in capsys.readouterr().out


@traces("REQ-003", "AC-02", "SPEC-003")
def test_cli_resolve_missing_and_task_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt resolve` missing-artifact errors, schema checks, and TASK target."""
    _seed_policies(tmp_path)
    assert main(["resolve", "ESC-404", "--by", "DEC-001", "--root", str(tmp_path)]) == 1
    assert "[CLI_ARTIFACT_NOT_FOUND]" in capsys.readouterr().out
    _write_document(
        tmp_path / "artifacts/escalations/ESC-001.md",
        "---\nid: ESC-001\nstatus: routed_to_agent\nresolved_by: null\n---\n",
    )
    assert main(["resolve", "ESC-001", "--by", "DEC-404", "--root", str(tmp_path)]) == 1
    assert "[CLI_ARTIFACT_NOT_FOUND]" in capsys.readouterr().out
    _write_document(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nstatus: planned\n---\n",
    )
    assert (
        main(["resolve", "ESC-001", "--by", "TASK-001", "--root", str(tmp_path)]) == 0
    )
    escalation, _ = parse_artifact_file(
        tmp_path / "artifacts/escalations/ESC-001.md", "ESC-001.md"
    )
    assert escalation and escalation.frontmatter["resolved_by"] == "TASK-001"


@traces("REQ-003", "AC-03", "SPEC-003")
def test_run_scheduled_tasks_worktree_execution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt run` executes eligible Tasks via MergeGate and updates status."""
    _seed_policies(tmp_path)
    assert main(["run", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    _write_document(tmp_path / "tests/helper_mod.py", "VALUE = 1\n")
    task_path = tmp_path / "artifacts/tasks/TASK-001.md"
    _write_document(
        task_path,
        "---\nid: TASK-001\ntype: test_contract\nstatus: planned\n"
        "depends_on: []\nrequired_files: []\nwrite_files: [tests/helper_mod.py]\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(1)'\"\n---\n",
    )
    assert main(["run", "--root", str(tmp_path)]) == 1
    assert "[GATE_VERIFY_CMD_FAILED]" in capsys.readouterr().out
    failed_document, _ = parse_artifact_file(task_path, "artifacts/tasks/TASK-001.md")
    assert failed_document and failed_document.frontmatter["status"] == "planned"
    _write_document(
        task_path,
        "---\nid: TASK-001\ntype: test_contract\nstatus: planned\n"
        "depends_on: []\nrequired_files: []\nwrite_files: [tests/helper_mod.py]\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(0)'\"\n---\n",
    )
    agent_script = (
        'python3 -c "from pathlib import Path; '
        "Path('tests/helper_mod.py').write_text('VALUE = 2\\n')\""
    )
    assert main(["run", "--agent-command", agent_script, "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "TASK-001"
    assert (tmp_path / "tests/helper_mod.py").read_text("utf-8") == "VALUE = 2\n"
    done_document, _ = parse_artifact_file(task_path, "artifacts/tasks/TASK-001.md")
    assert done_document and done_document.frontmatter["status"] == "done"


@traces("REQ-003", "AC-04", "SPEC-003")
def test_trace_lineage_and_documentation_generation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `mt trace` and `mt documentation` output lineage and live specs."""
    assert main(["trace", "REQ-003", "--root", str(REPOSITORY_ROOT)]) == 0
    output_requirement = capsys.readouterr().out
    for expected in ("INT-003", "REQ-003", "SPEC-003", "TASK-009", "TASK-010", "TEST"):
        assert expected in output_requirement
    target_python = "src/orchestrator/lifecycle.py"
    assert main(["trace", target_python, "--root", str(REPOSITORY_ROOT)]) == 0
    output_file = capsys.readouterr().out
    assert "SPEC-003" in output_file
    assert (
        "tests/test_lifecycle.py:test_trace_lineage_and_documentation_generation"
        in output_file
    )
    assert main(["documentation", "--root", str(REPOSITORY_ROOT)]) == 0
    documentation_output = capsys.readouterr().out
    for heading in (
        "## 1. Architecture & Layer Boundaries",
        "## 2. Agent WriteScope & Permission Topology",
        "## 3. Artifact State Lifecycles",
        "## 5. Live Repository Traceability Graph",
    ):
        assert heading in documentation_output


def _git_commit_all(root: Path, commit_message: str) -> None:
    """Configure git user and commit all files in root."""
    for git_command in (
        ["git", "config", "user.email", "mt@example.com"],
        ["git", "config", "user.name", "mt"],
        ["git", "add", "."],
        ["git", "commit", "-q", "-m", commit_message],
    ):
        subprocess.run(git_command, cwd=root, check=True)


def _seed_git_task_repository(root: Path, task_body: str) -> Path:
    """Initialize a Git repository with strict clean-worktree policy and a Task."""
    assert main(["initialize", "--root", str(root)]) == 0
    _seed_policies(root)
    permissions = load_yaml_file(root / "policy/permissions.yaml")
    permissions["clean_repo_invariants"]["require_empty_git_status_before_worktree"] = (
        True
    )
    _write_document(root / "policy/permissions.yaml", yaml.safe_dump(permissions))
    _write_document(root / "tests/helper_mod.py", "VALUE = 1\n")
    task_file = root / "artifacts/tasks/TASK-001.md"
    _write_document(task_file, task_body)
    _git_commit_all(root, "TASK-001: Seed initial task [traces: TASK-001]")
    _write_document(root / "uncommitted.txt", "dirty\n")
    with pytest.raises(RuntimeError):
        create_worktree(root, "dirty-wt")
    (root / "uncommitted.txt").unlink()
    return task_file


@traces("REQ-002", "AC-04", "SPEC-002")
@traces("REQ-003", "AC-03", "SPEC-003")
def test_run_with_git_commit_and_escalation_reroute_cap(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt run` auto-commits, clean worktrees, and 1-reroute Escalation cap."""
    task_body = (
        "---\nid: TASK-001\ntitle: Verify git run\ntype: test_contract\n"
        "status: planned\ndepends_on: []\nrequired_files: []\n"
        "write_files: [tests/helper_mod.py]\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(0)'\"\n---\n"
    )
    task_file = _seed_git_task_repository(tmp_path, task_body)
    escalate_one = (
        'python3 -c "from pathlib import Path; '
        "Path('artifacts/escalations/ESC-001.md')"
        ".write_text('---\\nid: ESC-001\\ntask_or_stage: TASK-001\\n"
        "reason_category: infeasible_scope\\nstatus: open\\n---\\n')\""
    )
    assert main(["run", "--agent-command", escalate_one, "--root", str(tmp_path)]) == 1
    assert "'planner-agent' (rescope_task)" in capsys.readouterr().out
    assert get_git_changed_files(tmp_path) == []
    _write_document(task_file, task_body)
    _git_commit_all(tmp_path, "TASK-001: Replan task [traces: TASK-001]")
    escalate_two = escalate_one.replace("ESC-001", "ESC-002")
    assert main(["run", "--agent-command", escalate_two, "--root", str(tmp_path)]) == 1
    assert "'human' (reroute_limit_reached)" in capsys.readouterr().out
    _write_document(task_file, task_body)
    _git_commit_all(tmp_path, "TASK-001: Retry task [traces: TASK-001]")
    delete_script = (
        "python3 -c \"from pathlib import Path; Path('tests/helper_mod.py').unlink()\""
    )
    assert main(["run", "--agent-command", delete_script, "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "TASK-001"
    assert get_git_changed_files(tmp_path) == []
    assert main(["trace", "TASK-001", "--root", str(tmp_path)]) == 0
    assert "COMMIT " in capsys.readouterr().out


@traces("REQ-004", "AC-02", "SPEC-004")
def test_role_prompt_synthesis_and_context_assembly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `mt prompt` for all 5 roles, target context, and error findings."""
    assert main(["prompt", "unknown-role", "--root", str(REPOSITORY_ROOT)]) == 1
    assert "[CLI_UNKNOWN_AGENT_ROLE]" in capsys.readouterr().out
    missing_args = ["prompt", "worker-agent", "--target", "TASK-999", "--root"]
    assert main([*missing_args, str(REPOSITORY_ROOT)]) == 1
    assert "[CLI_ARTIFACT_NOT_FOUND]" in capsys.readouterr().out
    for role in (
        "requirement-agent",
        "specification-agent",
        "planner-agent",
        "worker-agent",
        "review-agent",
    ):
        assert main(["prompt", role, "--root", str(REPOSITORY_ROOT)]) == 0
        assert f"# Role Prompt: `{role}`" in capsys.readouterr().out
    target_args = ["prompt", "worker-agent", "--target", "TASK-002", "--root"]
    assert main([*target_args, str(REPOSITORY_ROOT)]) == 0
    scoped_output = capsys.readouterr().out
    assert "### Artifact `TASK-002`" in scoped_output
    assert "### Artifact `SPEC-001`" in scoped_output
    assert "### Required File `tests/test_checkers.py`" in scoped_output


@traces("REQ-004", "AC-02", "SPEC-004")
@traces("REQ-004", "AC-03", "SPEC-004")
def test_worktree_run_provides_prompt_file_and_role_env(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify `mt approve` marks Intent processed and `mt run` sets MT_PROMPT_FILE."""
    task_body = (
        "---\nid: TASK-001\ntitle: Verify prompt env\ntype: test_contract\n"
        "status: planned\ndepends_on: []\nrequired_files: []\n"
        "write_files: [tests/helper_mod.py]\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(0)'\"\n---\n"
    )
    _seed_git_task_repository(tmp_path, task_body)
    _write_document(
        tmp_path / "artifacts/intents/INT-001.md",
        "---\nid: INT-001\nstatus: open\ncreated_at: '2026-10-16T00:00:00Z'\n---\nOk\n",
    )
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\nstatus: draft\ntraces_to: [INT-001]\n---\n"
        "## Statement\nOk\n",
    )
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    intent_doc, _ = parse_artifact_file(
        tmp_path / "artifacts/intents/INT-001.md", "INT-001.md"
    )
    assert intent_doc and intent_doc.frontmatter["status"] == "processed"
    _git_commit_all(tmp_path, "REQ-001: Approve requirement [traces: INT-001, REQ-001]")
    agent_script = (
        'python3 -c "import os; from pathlib import Path; '
        "prompt = Path(os.environ['MT_PROMPT_FILE']).read_text(); "
        "assert os.environ['MT_AGENT_ROLE'] == 'worker-agent'; "
        "assert 'TASK-001' in prompt; "
        "Path('tests/helper_mod.py').write_text('VALUE = 2\\n')\""
    )
    assert main(["run", "--agent-command", agent_script, "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "TASK-001"
