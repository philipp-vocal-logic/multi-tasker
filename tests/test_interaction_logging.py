"""Executable TestContracts for REQ-011 and SPEC-011 interaction logging."""

import importlib
from pathlib import Path
import sys
from typing import Any

import yaml

from src.cli.main import main
from src.domain.models import traces
from src.domain.parser import load_yaml_file
from src.orchestrator.documentation_generator import write_repository_documentation

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _seed_test_repository(target_root: Path) -> None:
    """Copy canonical policy files into target_root and initialize directories."""
    (target_root / "policy").mkdir(parents=True, exist_ok=True)
    for policy_file in (REPOSITORY_ROOT / "policy").glob("*.yaml"):
        content = policy_file.read_text(encoding="utf-8")
        (target_root / "policy" / policy_file.name).write_text(
            content, encoding="utf-8"
        )
    clean_path = target_root / "policy" / "clean_code.yaml"
    clean_policy = load_yaml_file(clean_path)
    clean_policy["linters"]["ruff"]["enabled"] = False
    clean_policy["linters"]["mypy"]["enabled"] = False
    clean_path.write_text(yaml.safe_dump(clean_policy), encoding="utf-8")
    main(["initialize", "--root", str(target_root)])


def _assert_cli_task_logs(tmp_path: Path, logger_module: Any) -> None:
    """Assert Task-specific CLI logs and separation from specification report."""
    task_one_events = logger_module.read_task_log(tmp_path, "TASK-001")
    assert len(task_one_events) == 1
    assert task_one_events[0]["event_type"] == "cli_invocation"
    assert task_one_events[0]["command"] == "check"
    assert task_one_events[0]["agent_role"] == "worker-agent"
    assert task_one_events[0]["exit_code"] == 0
    assert isinstance(task_one_events[0]["duration_ms"], int)
    task_two_events = logger_module.read_task_log(tmp_path, "TASK-002")
    assert len(task_two_events) == 1
    assert task_two_events[0]["command"] == "schedule"
    assert task_two_events[0]["model"] == "gemini-3.8-flash-high"
    assert task_two_events[0]["environment"] == "agy"
    spec_report = write_repository_documentation(tmp_path).read_text(encoding="utf-8")
    assert "cli_invocation" not in spec_report


@traces("REQ-011", "AC-01", "SPEC-011")
def test_cli_invocations_logged_to_events_and_task_logs(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """Verify all mt CLI commands log JSONL events and preserve separation."""
    _seed_test_repository(tmp_path)
    logger_module = importlib.import_module("src.orchestrator.interaction_logger")
    assert main(["intent", "Capture CLI telemetry", "--root", str(tmp_path)]) == 0
    check_args = [
        "check",
        "schemas",
        "--task",
        "TASK-001",
        "--agent",
        "worker-agent",
        "--root",
        str(tmp_path),
    ]
    assert main(check_args) == 0
    monkeypatch.setenv("MT_TASK_ID", "TASK-002")
    monkeypatch.setenv("MT_AGENT_ROLE", "worker-agent")
    monkeypatch.setenv("MT_AGENT_MODEL", "gemini-3.8-flash-high")
    monkeypatch.setenv("MT_EXECUTION_ENVIRONMENT", "agy")
    assert main(["schedule", "--root", str(tmp_path)]) == 0
    gitignore_file = tmp_path / ".report" / ".gitignore"
    assert gitignore_file.read_text(encoding="utf-8") == "*\n"
    commands = [entry["command"] for entry in logger_module.read_event_log(tmp_path)]
    assert {"initialize", "intent", "check", "schedule"}.issubset(commands)
    _assert_cli_task_logs(tmp_path, logger_module)


def _write_worker_helper_script(script_path: Path, cli_script: Path) -> None:
    """Write a worker script that runs an in-Worktree mt command and edits target."""
    script_content = (
        "import os, subprocess, sys\n"
        "from pathlib import Path\n"
        f"subprocess.run([sys.executable, '{cli_script.as_posix()}', 'schedule', "
        "'--root', '.'], check=True)\n"
        "target = os.environ.get('MT_WRITE_FILES', '').split(',')[0]\n"
        "if target:\n"
        "    Path(target).parent.mkdir(parents=True, exist_ok=True)\n"
        "    Path(target).write_text('VALUE = 1\\n', encoding='utf-8')\n"
    )
    script_path.write_text(script_content, encoding="utf-8")


def _write_task_artifact(
    tmp_path: Path, task_id: str, write_target: str, verification_cmd: str
) -> None:
    """Write a ready test_contract Task artifact under tmp_path."""
    task_path = tmp_path / "artifacts" / "tasks" / f"{task_id}.md"
    task_path.write_text(
        f"---\nid: {task_id}\ntitle: Logged Task {task_id}\ntype: test_contract\n"
        "status: ready\ntraces_to:\n  - REQ-001\ndepends_on: []\n"
        f"required_files: []\nwrite_files:\n  - {write_target}\n"
        f'verification_cmd: "{verification_cmd}"\n---\n'
        f"## Objective\nExecute {task_id}.\n\n"
        f"## Scoped Instructions\nWrite {write_target}.\n",
        encoding="utf-8",
    )


@traces("REQ-011", "AC-02", "SPEC-011")
def test_worktree_task_execution_and_merge_gate_logs_merged(tmp_path: Path) -> None:
    """Verify Worktree agent, CLI, and MergeGate logs merge onto BaseBranch."""
    _seed_test_repository(tmp_path)
    logger_module = importlib.import_module("src.orchestrator.interaction_logger")
    worker_script = tmp_path / ".report" / "worker_helper.py"
    _write_worker_helper_script(
        worker_script, REPOSITORY_ROOT / "src" / "cli" / "main.py"
    )
    agent_cmd = f"{sys.executable} {worker_script.as_posix()}"
    _write_task_artifact(
        tmp_path, "TASK-001", "tests/test_logged.py", "python3 -c 'assert True'"
    )
    assert main(["run", "--agent-command", agent_cmd, "--root", str(tmp_path)]) == 0
    task_one_logs = logger_module.read_task_log(tmp_path, "TASK-001")
    assert [entry["event_type"] for entry in task_one_logs] == [
        "cli_invocation",
        "agent_invocation",
        "merge_gate",
    ]
    assert task_one_logs[0]["command"] == "schedule"
    assert task_one_logs[1]["details"]["return_code"] == 0
    assert task_one_logs[2]["details"]["passed"] is True
    assert task_one_logs[2]["details"]["changed_files"] == ["tests/test_logged.py"]
    _write_task_artifact(
        tmp_path, "TASK-002", "tests/test_failed.py", "python3 -c 'assert False'"
    )
    assert main(["run", "--agent-command", agent_cmd, "--root", str(tmp_path)]) == 1
    task_two_logs = logger_module.read_task_log(tmp_path, "TASK-002")
    assert [entry["event_type"] for entry in task_two_logs] == [
        "cli_invocation",
        "agent_invocation",
        "merge_gate",
    ]
    assert task_two_logs[2]["details"]["passed"] is False
    assert task_two_logs[2]["details"]["findings"]
