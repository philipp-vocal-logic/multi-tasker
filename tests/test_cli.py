"""TestContracts for zero-noise CLI output and check runner dispatch."""

from pathlib import Path

import pytest

from multi_tasker.checkers.runner import run_single_check
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _write_document(path: Path, content: str) -> None:
    """Create parent directories and write file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@traces("REQ-001", "AC-05", "SPEC-001")
def test_cli_failure_output_and_unknown_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify CLI emits formatted single-line Findings and exits 1 on failure."""
    unknown = run_single_check("nonexistent", tmp_path)
    assert unknown[0].rule_id == "CHECK_UNKNOWN"
    exit_code = main(["check", "permissions", "--root", str(tmp_path)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "[PERM_POLICY_MISSING]" in captured.out
    assert captured.err == ""


@traces("REQ-001", "AC-05", "SPEC-001")
def test_self_check_passes_with_zero_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Run `mt check all` on this repository and assert exit 0 with 0 bytes."""
    exit_code = main(["check", "all", "--root", str(REPOSITORY_ROOT)])
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
    assert exit_code == 0


@traces("REQ-025", "AC-01", "SPEC-025")
def test_fail_fast_worker_task_scope_and_explicit_check_paths(tmp_path: Path) -> None:
    """Verify worker-agent fails fast on missing --task and runner forwards --paths."""
    from multi_tasker.orchestrator.lifecycle import bootstrap_evaluation_repository
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt

    eval_root = tmp_path / "fail_fast_repo"
    bootstrap_evaluation_repository(eval_root, "Verify fail-fast worker check.")
    empty_diff_findings = run_single_check(
        "permissions", eval_root, target_paths=[], agent_role="worker-agent"
    )
    assert any(item.rule_id == "PERM_TASK_ID_MISSING" for item in empty_diff_findings)
    _write_document(
        eval_root / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\ntitle: Test Task\ntype: test_contract\n"
        "status: in_progress\ntraces_to: [REQ-001, SPEC-001]\ndepends_on: []\n"
        "required_files: []\nwrite_files: [tests/test_calc.py]\n"
        "verification_cmd: python3 -m py_compile tests/test_calc.py\n---\n"
        "## Objective\nO.\n\n## Scoped Instructions\nI.\n",
    )
    _write_document(
        eval_root / "tests/test_calc.py", "def test_ok() -> None:\n    pass\n"
    )
    scoped = run_single_check(
        "permissions",
        eval_root,
        target_paths=["tests/test_calc.py"],
        agent_role="worker-agent",
        task_id="TASK-001",
    )
    assert scoped == []
    auto_diff = run_single_check(
        "permissions", eval_root, agent_role="worker-agent", task_id="TASK-001"
    )
    assert auto_diff == []
    worker_prompt, errors = build_agent_prompt(eval_root, "worker-agent", "TASK-001")
    assert not errors
    assert "--agent worker-agent --task TASK-001 --paths" in worker_prompt
