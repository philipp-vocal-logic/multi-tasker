"""TestContracts for task_runner Worktree execution and module sizing ceilings."""

import importlib
from pathlib import Path
import subprocess

import pytest
import yaml

from multi_tasker.checkers import common
from multi_tasker.cli.main import main
from multi_tasker.domain import parser as domain_parser
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file, parse_artifact_file
from multi_tasker.orchestrator.worktree import create_worktree
from tests.test_lifecycle import REPOSITORY_ROOT, _seed_policies, _write_document
from tests.test_orchestrator import _seed_minimal_policies


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
    execution = load_yaml_file(root / "policy/agent_execution.yaml")
    execution["clean_repo_invariants"]["require_empty_git_status_before_worktree"] = (
        True
    )
    _write_document(root / "policy/agent_execution.yaml", yaml.safe_dump(execution))
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
    assert common.get_git_changed_files(tmp_path) == []
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
    assert common.get_git_changed_files(tmp_path) == []
    assert main(["trace", "TASK-001", "--root", str(tmp_path)]) == 0
    assert "COMMIT " in capsys.readouterr().out


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


@traces("REQ-005", "AC-01", "SPEC-005")
@traces("REQ-005", "AC-02", "SPEC-005")
def test_execution_environment_and_model_resolution(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CLI > Task > Policy model precedence and template expansion in mt run."""
    task_body = (
        "---\nid: TASK-001\ntitle: Verify model env\ntype: test_contract\n"
        "status: planned\ndepends_on: []\nrequired_files: []\n"
        "write_files: [tests/helper_mod.py]\nmodel: gemini-3.8-flash-medium\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(0)'\"\n---\n"
    )
    _seed_git_task_repository(tmp_path, task_body)
    script = (
        'python3 -c "import os, sys; from pathlib import Path; '
        "assert os.environ['MT_AGENT_MODEL'] == 'gemini-3.8-flash-low'; "
        "assert os.environ['MT_EXECUTION_ENVIRONMENT'] == 'agy'; "
        "assert sys.argv[1] == 'gemini-3.8-flash-low'; "
        "Path('tests/helper_mod.py').write_text('VALUE = 3\\n')\" {model}"
    )
    run_args = ["run", "--agent-command", script, "--model", "gemini-3.8-flash-low"]
    assert main([*run_args, "--environment", "agy", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "TASK-001"


@traces("REQ-008", "AC-01", "SPEC-008")
@traces("REQ-008", "AC-02", "SPEC-008")
def test_atomic_approve_and_failed_run_preserve_clean_base(tmp_path: Path) -> None:
    """Verify failed mt approve and failed mt run do not mutate BaseBranch files."""
    _seed_minimal_policies(tmp_path)
    real_schemas = load_yaml_file(REPOSITORY_ROOT / "policy/artifact_schemas.yaml")
    _write_document(
        tmp_path / "policy/artifact_schemas.yaml", yaml.safe_dump(real_schemas)
    )
    requirement_file = tmp_path / "artifacts/requirements/REQ-001.md"
    _write_document(requirement_file, "---\nid: REQ-001\nstatus: draft\n---\n")
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 1
    req_doc, _ = domain_parser.parse_artifact_file(requirement_file, "REQ-001.md")
    assert req_doc and req_doc.frontmatter["status"] == "draft"
    _seed_minimal_policies(tmp_path)
    _write_document(tmp_path / "tests/t1.py", "X = 1\n")
    task_file = tmp_path / "artifacts/tasks/TASK-001.md"
    _write_document(
        task_file,
        "---\nid: TASK-001\ntype: test_contract\nstatus: planned\n"
        "depends_on: []\nrequired_files: []\nwrite_files:\n  - tests/t1.py\n"
        "verification_cmd: \"python3 -c 'raise SystemExit(1)'\"\n---\n",
    )
    original_task_text = task_file.read_text(encoding="utf-8")
    assert main(["run", "--root", str(tmp_path)]) == 1
    assert task_file.read_text(encoding="utf-8") == original_task_text


@traces("REQ-009", "AC-01", "SPEC-009")
@traces("REQ-009", "AC-02", "SPEC-009")
@traces("REQ-018", "AC-01", "SPEC-018")
@traces("REQ-018", "AC-02", "SPEC-018")
@traces("REQ-026", "AC-01", "SPEC-026")
@traces("REQ-045", "AC-03", "SPEC-045")
def test_modular_refactoring_and_file_size_ceilings(tmp_path: Path) -> None:
    """Verify module decomposition, 500-line ceiling, and 400-line refactor hints."""
    task_runner = importlib.import_module("multi_tasker.orchestrator.task_runner")
    lifecycle = importlib.import_module("multi_tasker.orchestrator.lifecycle")
    code_git_trace = importlib.import_module(
        "multi_tasker.checkers.code_and_git_traceability"
    )
    traceability_module = importlib.import_module(
        "multi_tasker.checkers.traceability_checker"
    )
    limits_module = importlib.import_module("multi_tasker.checkers.limits_checker")
    prompt_module = importlib.import_module("multi_tasker.orchestrator.prompt_builder")
    assert callable(getattr(task_runner, "run_scheduled_tasks", None))
    assert not hasattr(lifecycle, "run_scheduled_tasks")
    for func_name in (
        "check_test_contract_coverage",
        "check_specification_target_files",
        "check_git_commit_history",
    ):
        assert callable(getattr(code_git_trace, func_name, None))
        assert not hasattr(traceability_module, func_name)
    root = Path(__file__).resolve().parent.parent
    limits_policy = load_yaml_file(root / "policy" / "code_limits.yaml")["source_code"]
    max_lines = int(limits_policy["max_file_lines"])
    assert max_lines == 500 and int(limits_policy["refactor_target_file_lines"]) == 400
    for folder in ("src", "tests"):
        for py_file in (root / folder).rglob("*.py"):
            line_count = len(py_file.read_text(encoding="utf-8").splitlines())
            assert line_count <= max_lines, f"{py_file} has {line_count} lines"
    assert [path.name for path in (root / "tests").glob("test_*_and_*.py")] == []
    assert limits_module.collect_refactoring_targets(root) == []
    _seed_policies(tmp_path)
    _write_document(
        tmp_path / "src" / "large_module.py",
        '"""Large module."""\n' + "\n".join(f"VAL_{idx} = {idx}" for idx in range(405)),
    )
    assert limits_module.check_limits(tmp_path) == []
    hints = limits_module.collect_refactoring_targets(tmp_path)
    assert len(hints) == 1 and hints[0].rule_id == "LIMIT_REFACTOR_HINT"
    for role in ("specification-agent", "planner-agent"):
        prompt_text, errors = prompt_module.build_agent_prompt(tmp_path, role)
        assert not errors and "Refactoring Targets (Warning)" in prompt_text
        assert "src/large_module.py" in prompt_text
