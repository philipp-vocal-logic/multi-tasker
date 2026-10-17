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
    resolve_args = ["resolve", "ESC-001", "--by", "TASK-001", "--root", str(tmp_path)]
    assert main(resolve_args) == 0
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
        "verification_cmd: python3 -c \"print('E   boom'); "
        "print('FAILED t'); raise SystemExit(1)\"\n---\n",
    )
    assert main(["run", "--root", str(tmp_path)]) == 1
    assert "E   boom | FAILED t" in capsys.readouterr().out
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
    expected_test = "test_trace_lineage_and_documentation_generation"
    assert f"tests/test_lifecycle.py:{expected_test}" in output_file
    assert main(["documentation", "--root", str(REPOSITORY_ROOT)]) == 0
    documentation_output = capsys.readouterr().out
    for heading in (
        "## 1. Architecture & Layer Boundaries",
        "## 2. Agent WriteScope & Permission Topology",
        "## 3. Artifact State Lifecycles",
        "## 5. Live Repository Traceability Graph",
    ):
        assert heading in documentation_output


@traces("REQ-010", "AC-01", "SPEC-010")
@traces("REQ-010", "AC-02", "SPEC-010")
def test_multi_wave_run_and_approval_traceability_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify multi-wave mt run, E-line verify failures, and approve traceability."""
    _seed_policies(tmp_path)
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\nstatus: draft\ntraces_to: [INT-999]\n---\n"
        "## Statement\nOk\n",
    )
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 1
    assert "[TRACE_MISSING_REF]" in capsys.readouterr().out
    _write_document(tmp_path / "tests/w1.py", "VALUE = 1\n")
    _write_document(tmp_path / "tests/w2.py", "VALUE = 2\n")
    for task_id, deps, writes in (
        ("TASK-001", "[]", "[tests/w1.py]"),
        ("TASK-002", "[TASK-001]", "[tests/w2.py]"),
    ):
        _write_document(
            tmp_path / f"artifacts/tasks/{task_id}.md",
            f"---\nid: {task_id}\ntype: test_contract\nstatus: planned\n"
            f"depends_on: {deps}\nrequired_files: []\nwrite_files: {writes}\n"
            "verification_cmd: \"python3 -c 'raise SystemExit(0)'\"\n---\n",
        )
    assert main(["run", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip().splitlines() == ["TASK-001", "TASK-002"]
