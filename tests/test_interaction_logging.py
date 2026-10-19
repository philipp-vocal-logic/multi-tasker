"""Executable TestContracts for REQ-011/SPEC-011 and REQ-012/SPEC-012."""

import importlib
from pathlib import Path
import sys
from typing import Any

import yaml

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.checkers.permissions_checker import check_permissions
import pytest

from multi_tasker.cli.main import build_parser, main
from multi_tasker.domain.models import ArtifactDocument, traces
from multi_tasker.domain.parser import load_yaml_file
from multi_tasker.orchestrator.documentation_generator import (
    generate_external_agents_guide,
    write_repository_documentation,
)
from multi_tasker.orchestrator.prompt_builder import (
    build_agent_prompt,
    prepare_worker_invocation,
)

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
    logger_module = importlib.import_module(
        "multi_tasker.orchestrator.interaction_logger"
    )
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
    logger_module = importlib.import_module(
        "multi_tasker.orchestrator.interaction_logger"
    )
    worker_script = tmp_path / ".report" / "worker_helper.py"
    _write_worker_helper_script(
        worker_script, REPOSITORY_ROOT / "src" / "multi_tasker" / "cli" / "main.py"
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


@traces("REQ-012", "AC-01", "SPEC-012")
@traces("REQ-028", "AC-02", "SPEC-028")
def test_context_mode_policy_validation_and_precedence(tmp_path: Path) -> None:
    """Verify execution_environments validation without context_mode branching."""
    _seed_test_repository(tmp_path)
    prompt_module = importlib.import_module("multi_tasker.orchestrator.prompt_builder")
    assert not hasattr(prompt_module, "resolve_context_mode")
    assert not hasattr(prompt_module, "VALID_CONTEXT_MODES")
    permissions_path = tmp_path / "policy" / "permissions.yaml"
    permissions = load_yaml_file(permissions_path)
    assert "default_context_mode" not in permissions.get("execution_environments", {})
    permissions["execution_environments"]["default_environment"] = "missing"
    permissions_path.write_text(yaml.safe_dump(permissions), encoding="utf-8")
    findings = check_permissions(tmp_path)
    assert any(item.rule_id == "PERM_INVALID_EXEC_ENV" for item in findings)


def _assert_self_contained_prompt_output(capsys: Any) -> None:
    """Assert mt prompt outputs Execution Steps and Architecture Layers."""
    prompt_args = [
        "prompt",
        "worker-agent",
        "--target",
        "TASK-002",
        "--root",
        str(REPOSITORY_ROOT),
    ]
    assert main(prompt_args) == 0
    prompt_output = capsys.readouterr().out
    assert "Self-Contained Context" in prompt_output
    assert "Execution Steps" in prompt_output
    assert "mt check all --agent worker-agent --task TASK-002 --paths" in prompt_output
    assert "./mt check all" not in prompt_output
    assert "Architecture Layers" in prompt_output
    assert '@traces("REQ-NNN", "AC-XX", "SPEC-NNN")' in prompt_output
    assert "### `TASK` Output Contract" not in prompt_output
    assert "&& pytest -q tests/test_checkers.py" in prompt_output
    assert "Forbidden Synonyms" in prompt_output
    assert "def test_permissions_checker_matrix" in prompt_output
    assert "class Finding" in prompt_output


@traces("REQ-012", "AC-02", "SPEC-012")
@traces("REQ-028", "AC-01", "SPEC-028")
@traces("REQ-030", "AC-01", "SPEC-030")
@traces("REQ-030", "AC-02", "SPEC-030")
@traces("REQ-031", "AC-01", "SPEC-031")
@traces("REQ-031", "AC-02", "SPEC-031")
def test_prompt_and_worktree_run_context_modes(tmp_path: Path, capsys: Any) -> None:
    """Verify self-contained prompt synthesis and Worktree execution."""
    _assert_self_contained_prompt_output(capsys)
    _seed_test_repository(tmp_path)
    _write_task_artifact(
        tmp_path, "TASK-001", "tests/test_mode.py", "python3 -c 'assert True'"
    )
    worker_cmd = (
        'python3 -c "import os; from pathlib import Path; '
        "assert 'MT_CONTEXT_MODE' not in os.environ; "
        "prompt = Path(os.environ['MT_PROMPT_FILE']).read_text('utf-8'); "
        "assert 'Self-Contained Context' in prompt; "
        "assert 'Execution Steps' in prompt; "
        "Path('tests/test_mode.py').write_text('MODE = 1\\n')\""
    )
    run_args = ["run", "--agent-command", worker_cmd]
    assert main([*run_args, "--root", str(tmp_path)]) == 0


def _write_file(path: Path, text: str) -> None:
    """Create parent folders and write text content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@traces("REQ-016", "AC-01", "SPEC-016")
@traces("REQ-017", "AC-01", "SPEC-017")
def test_initialize_scaffolds_default_policies_and_gitignore(tmp_path: Path) -> None:
    """Verify mt initialize scaffolds policy/*.yaml, .gitignore, and AGENTS.md."""
    custom_limits = "source_code:\n  max_file_lines: 777\n"
    _write_file(tmp_path / "policy/limits.yaml", custom_limits)
    _write_file(tmp_path / ".gitignore", "__pycache__/\n")
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "policy/limits.yaml").read_text("utf-8") == custom_limits
    architecture = load_yaml_file(tmp_path / "policy/architecture.yaml")
    assert "multi_tasker" in architecture.get("allowed_third_party_packages", [])
    gitignore_lines = (tmp_path / ".gitignore").read_text("utf-8").splitlines()
    for entry in ("__pycache__/", ".worktrees/", ".report/", ".mt_prompt.md"):
        assert entry in gitignore_lines
    agents_guide = (tmp_path / "AGENTS.md").read_text("utf-8")
    for expected in (
        "policy/architecture.yaml",
        "PERM_POLICY_MODIFIED",
        "from multi_tasker.domain.models import traces",
    ):
        assert expected in agents_guide
    _write_file(tmp_path / "AGENTS.md", "# Custom Guide\n")
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    assert (tmp_path / "AGENTS.md").read_text("utf-8") == "# Custom Guide\n"


@traces("REQ-016", "AC-02", "SPEC-016")
@traces("REQ-026", "AC-02", "SPEC-026")
def test_architecture_custom_package_and_worktree_pythonpath(tmp_path: Path) -> None:
    """Verify custom package prefixes in check_architecture and worktree PYTHONPATH."""
    architecture_policy = {
        "dependency_rules": {"forbid_circular_imports": True},
        "allowed_third_party_packages": ["multi_tasker"],
        "layers": [
            {
                "name": "core",
                "paths": ["app/core/**"],
                "allowed_internal_imports": ["app.core"],
                "forbidden_internal_imports": ["app.api"],
            },
            {
                "name": "api",
                "paths": ["app/api/**"],
                "allowed_internal_imports": ["app.core", "app.api"],
            },
        ],
    }
    _write_file(
        tmp_path / "policy/architecture.yaml", yaml.safe_dump(architecture_policy)
    )
    _write_file(
        tmp_path / "app/core/first.py",
        "from multi_tasker.domain.models import traces\n"
        "from app.api import routes\nfrom app.core import second\n",
    )
    _write_file(tmp_path / "app/core/second.py", "from app.core import first\n")
    _write_file(tmp_path / "app/api/routes.py", "VALUE = 1\n")
    rules = {finding.rule_id for finding in check_architecture(tmp_path)}
    assert rules == {"ARCH_FORBIDDEN_IMPORT", "ARCH_CIRCULAR_IMPORT"}
    document = ArtifactDocument(
        "artifacts/tasks/TASK-001.md", "TASK", {"id": "TASK-001"}, "", 1, {}
    )
    _, env = prepare_worker_invocation(
        tmp_path, document, tmp_path / ".mt_prompt.md", ("echo", "agy", "m")
    )
    assert env["PYTHONPATH"] == str(tmp_path)


@traces("REQ-020", "AC-01", "SPEC-020")
@traces("REQ-020", "AC-02", "SPEC-020")
def test_intent_why_guidance_in_prompt_cli_and_agents_guide(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify Intent why guidance in RequirementAgent prompt, CLI help, and guide."""
    prompt_text, findings = build_agent_prompt(REPOSITORY_ROOT, "requirement-agent")
    assert findings == []
    assert (
        "translating its requested change and motivating reason into testable "
        "AcceptanceCriteria and ImpactAnalysis" in prompt_text
    )
    assert "mt intent '<what to change and why>'" in generate_external_agents_guide()
    with pytest.raises(SystemExit):
        build_parser().parse_args(["intent", "--help"])
    intent_help = capsys.readouterr().out
    assert (
        "Intent statement describing what to change and why (or file path)."
        in intent_help
    )


@traces("REQ-022", "AC-01", "SPEC-022")
@traces("REQ-022", "AC-02", "SPEC-022")
def test_pipeline_suitability_evaluation_and_per_role_telemetry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify mt run --evaluate bootstraps repo and emits role suitability JSON."""
    import json

    stage_test_mod = importlib.import_module("tests.test_stage_runner")
    eval_root = tmp_path / "eval_repo"
    script_path = tmp_path / "eval_agent.py"
    script_path.write_text(stage_test_mod._GIT_PIPELINE_SCRIPT, encoding="utf-8")
    eval_args = [
        "run",
        "--evaluate",
        "Add calculation helper to measure pipeline suitability.",
        "--agent-command",
        f"{sys.executable} {script_path.as_posix()}",
        "--root",
        str(eval_root),
    ]
    assert main(eval_args) == 0
    summary = json.loads(capsys.readouterr().out.strip())
    assert summary["passed"] is True
    assert summary["gate_pass_rate"] == 1.0
    assert "TASK-001" in summary["completed_artifacts"]
    assert "TASK-002" in summary["completed_artifacts"]
    expected_roles = {
        "requirement-agent",
        "specification-agent",
        "planner-agent",
        "review-agent",
        "worker-agent",
    }
    assert set(summary["role_invocations"]) == expected_roles
    assert set(summary["role_durations_ms"]) == expected_roles
