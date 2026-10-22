"""TestContracts for CLI lifecycle and documentation commands (`mt initialize`)."""

from pathlib import Path
import subprocess
from typing import Any

import pytest
import yaml

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.checkers.permissions_checker import check_permissions
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file, parse_artifact_file
from multi_tasker.orchestrator.worktree import (
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
    real_permissions = load_yaml_file(REPOSITORY_ROOT / "policy/agent_permissions.yaml")
    real_lifecycle = load_yaml_file(REPOSITORY_ROOT / "policy/artifact_lifecycle.yaml")
    permissions: dict[str, Any] = {
        "global_forbidden_write": ["policy/**"],
        "agents": real_permissions.get("agents", {}),
    }
    execution = {
        "clean_repo_invariants": {"require_empty_git_status_before_worktree": False}
    }
    traceability_rules = {
        "require_files_declared_in_spec_target_files": False,
        "require_spec_target_files_covered_by_tasks": False,
    }
    configurations: dict[str, dict[str, Any]] = {
        "agent_permissions.yaml": permissions,
        "agent_execution.yaml": execution,
        "glossary.yaml": {"enforcement": {}, "terms": []},
        "code_limits.yaml": {"source_code": {}},
        "code_quality.yaml": {"linters": {"ruff": {"enabled": False}}, "ast_rules": {}},
        "code_architecture.yaml": {
            "dependency_rules": {},
            "layers": [{"name": "tests", "paths": ["tests/**"]}],
        },
        "artifact_schemas.yaml": {"schemas": {}},
        "artifact_limits.yaml": {"artifacts": {}},
        "artifact_lifecycle.yaml": {
            "state_transitions": real_lifecycle.get("state_transitions", {}),
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


@traces("REQ-003", "AC-04", "SPEC-003")
def test_trace_lineage_and_documentation_generation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `mt trace` and `mt documentation` output lineage and live specs."""
    assert main(["trace", "REQ-003", "--root", str(REPOSITORY_ROOT)]) == 0
    output_requirement = capsys.readouterr().out
    for expected in ("INT-003", "REQ-003", "SPEC-003", "TASK-009", "TASK-010", "TEST"):
        assert expected in output_requirement
    target_python = "src/multi_tasker/orchestrator/lifecycle.py"
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


@traces("REQ-027", "AC-01", "SPEC-027")
@traces("REQ-027", "AC-02", "SPEC-027")
@traces("REQ-029", "AC-01", "SPEC-029")
def test_initialize_presets_and_invalid_preset_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify default python preset, multi-tasker preset, and CLI_INVALID_PRESET."""
    python_root = tmp_path / "python_project"
    assert main(["initialize", "--root", str(python_root)]) == 0
    python_arch = (python_root / "policy" / "code_architecture.yaml").read_text("utf-8")
    assert "src/domain/**" in python_arch
    assert "src/multi_tasker/domain/**" not in python_arch
    mt_root = tmp_path / "mt_project"
    assert main(["initialize", "--preset", "multi-tasker", "--root", str(mt_root)]) == 0
    mt_arch = (mt_root / "policy" / "code_architecture.yaml").read_text("utf-8")
    assert "src/multi_tasker/domain/**" in mt_arch
    bad_root = tmp_path / "bad_project"
    assert main(["initialize", "--preset", "invalid", "--root", str(bad_root)]) == 1
    assert "[CLI_INVALID_PRESET]" in capsys.readouterr().out


@traces("REQ-037", "AC-01", "SPEC-037")
@traces("REQ-037", "AC-02", "SPEC-037")
def test_multi_requirement_intent_processing_and_completion(
    tmp_path: Path,
) -> None:
    """Verify INT stays in processing until all linked REQs are approved."""
    _seed_policies(tmp_path)
    intent_path = tmp_path / "artifacts/intents/INT-001.md"
    _write_document(
        intent_path,
        '---\nid: INT-001\nstatus: open\ncreated_at: "2026-10-21T00:00:00Z"\n---\n'
        "Split into two atomic requirements.\n",
    )
    for req_id in ("REQ-001", "REQ-002"):
        _write_document(
            tmp_path / f"artifacts/requirements/{req_id}.md",
            f"---\nid: {req_id}\ntitle: Atomic {req_id}\nstatus: draft\n"
            "traces_to: [INT-001]\ndecisions: []\n"
            "acceptance_criteria: [{id: AC-01, given: a, when: b, then: c}]\n"
            "version: 1\n---\n## Statement\nOk.\n\n## Impact Analysis\nOk.\n",
        )
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    first_intent, _ = parse_artifact_file(intent_path, "artifacts/intents/INT-001.md")
    assert first_intent and first_intent.frontmatter["status"] == "processing"
    assert main(["approve", "REQ-002", "--root", str(tmp_path)]) == 0
    final_intent, _ = parse_artifact_file(intent_path, "artifacts/intents/INT-001.md")
    assert final_intent and final_intent.frontmatter["status"] == "processed"
