"""TestContracts for prompt_builder and prompt_context synthesis."""

from pathlib import Path
from typing import Any

import pytest

from multi_tasker.cli.main import build_parser, main
from multi_tasker.domain.models import traces
from multi_tasker.orchestrator.documentation_generator import (
    generate_external_agents_guide,
)
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from tests.test_interaction_logging import (
    REPOSITORY_ROOT,
    _seed_test_repository,
    _write_task_artifact,
)
from tests.test_orchestrator import _write_document


@traces("REQ-004", "AC-02", "SPEC-004")
def test_role_prompt_synthesis_and_context_assembly(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Verify `mt prompt` for all 5 roles, target context, and error findings."""
    repository_root = Path(__file__).resolve().parent.parent
    assert main(["prompt", "unknown-role", "--root", str(repository_root)]) == 1
    assert "[CLI_UNKNOWN_AGENT_ROLE]" in capsys.readouterr().out
    missing_args = ["prompt", "worker-agent", "--target", "TASK-999", "--root"]
    assert main([*missing_args, str(repository_root)]) == 1
    assert "[CLI_ARTIFACT_NOT_FOUND]" in capsys.readouterr().out
    for role in (
        "requirement-agent",
        "specification-agent",
        "planner-agent",
        "worker-agent",
        "review-agent",
    ):
        assert main(["prompt", role, "--root", str(repository_root)]) == 0
        assert f"# Role Prompt: `{role}`" in capsys.readouterr().out
    target_args = ["prompt", "worker-agent", "--target", "TASK-002", "--root"]
    assert main([*target_args, str(repository_root)]) == 0
    scoped_output = capsys.readouterr().out
    assert "### Artifact `TASK-002`" in scoped_output
    assert "### Artifact `SPEC-001`" in scoped_output
    assert "### Required File `tests/test_checkers.py`" in scoped_output


@traces("REQ-036", "AC-01", "SPEC-036")
@traces("REQ-036", "AC-02", "SPEC-036")
@traces("REQ-036", "AC-03", "SPEC-036")
def test_atomic_requirement_decomposition_prompt_and_catalog(
    tmp_path: Path,
) -> None:
    """Verify Requirement Decomposition Contract, catalog, and review rubric."""
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt

    assert main(["initialize", "--root", str(tmp_path)]) == 0
    assert main(["intent", "Add login and export.", "--root", str(tmp_path)]) == 0
    empty_prompt, errors = build_agent_prompt(tmp_path, "requirement-agent", "INT-001")
    assert not errors
    assert "Requirement Decomposition Contract" in empty_prompt
    assert "good" in empty_prompt and "edge" in empty_prompt
    assert "Existing Requirements Catalog" not in empty_prompt
    example_prompt, _ = build_agent_prompt(tmp_path, "requirement-agent")
    assert "Requirement Decomposition Contract" in example_prompt
    assert "`REQ-NNN`" in example_prompt
    assert "Existing Requirements Catalog" not in example_prompt
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\ntitle: User Login\nstatus: approved\n"
        "traces_to: [INT-001]\nversion: 1\n---\n",
    )
    catalog_prompt, _ = build_agent_prompt(tmp_path, "requirement-agent", "INT-001")
    assert "### Existing Requirements Catalog" in catalog_prompt
    assert "`REQ-001`: User Login (`status: approved`, `version: 1`)" in catalog_prompt
    review_prompt, _ = build_agent_prompt(tmp_path, "review-agent")
    assert "single cohesive capability per `REQ`" in review_prompt
    assert "good, edge, and failure" in review_prompt


def _assert_streamlined_stage_and_review_prompts() -> None:
    """Assert compact templates, cross-stage limits, and SPEC target_files context."""
    req_prompt, _ = build_agent_prompt(REPOSITORY_ROOT, "requirement-agent")
    assert (
        "json_schema:" not in req_prompt and "additionalProperties:" not in req_prompt
    )
    assert "```markdown\n---\nid: REQ-NNN" in req_prompt
    assert "id: ESC-NNN" in req_prompt and "id: ESC-001" not in req_prompt
    assert "id: AC-XX" in req_prompt and "id: AC-01" not in req_prompt
    assert all(len(line) <= 88 for line in req_prompt.splitlines())
    assert "Glossary Terms" in req_prompt and "req_id" in req_prompt
    assert "## Statement" in req_prompt and "## Impact Analysis" in req_prompt
    assert (
        "`status: in_review`" in req_prompt and "verdict: pass|fail" not in req_prompt
    )
    assert "@traces(" not in req_prompt and "Source Limits" not in req_prompt
    for role in ("specification-agent", "planner-agent", "review-agent"):
        role_prompt, _ = build_agent_prompt(REPOSITORY_ROOT, role)
        assert "Source Limits" in role_prompt and "Clean Code AST Rules" in role_prompt
    rev_prompt, _ = build_agent_prompt(REPOSITORY_ROOT, "review-agent", "SPEC-001")
    assert (
        "`verdict: pass|fail`" in rev_prompt and "status: in_review" not in rev_prompt
    )
    assert "artifacts/reviews/REV-" in rev_prompt
    assert "Target File `tests/test_checkers.py`" in rev_prompt
    assert "Semantic Review Rubric" in rev_prompt


def _assert_self_contained_prompt_output(capsys: Any) -> None:
    """Assert mt prompt outputs Execution Steps and Architecture Layers."""
    _assert_streamlined_stage_and_review_prompts()
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
    assert "Architecture Layers" in prompt_output and "imports:" in prompt_output
    assert "json_schema:" not in prompt_output
    assert '@traces("REQ-NNN", "AC-XX", "SPEC-NNN")' in prompt_output
    assert "### `TASK` Output Contract" not in prompt_output
    assert "&& pytest -q tests/test_checkers.py" in prompt_output
    assert "`max_line_length=88`" in prompt_output
    assert "### Python Source & `TestContract` Output Contract" in prompt_output
    assert "### Required File `artifacts/requirements/REQ-001.md`" not in prompt_output
    assert "Glossary Terms" in prompt_output and "Forbidden Synonyms" in prompt_output
    assert "def test_permissions_checker_matrix" in prompt_output
    assert "class Finding" in prompt_output


@traces("REQ-012", "AC-02", "SPEC-012")
@traces("REQ-028", "AC-01", "SPEC-028")
@traces("REQ-030", "AC-01", "SPEC-030")
@traces("REQ-030", "AC-02", "SPEC-030")
@traces("REQ-031", "AC-01", "SPEC-031")
@traces("REQ-031", "AC-02", "SPEC-031")
@traces("REQ-033", "AC-01", "SPEC-033")
@traces("REQ-033", "AC-02", "SPEC-033")
@traces("REQ-034", "AC-01", "SPEC-034")
@traces("REQ-034", "AC-02", "SPEC-034")
@traces("REQ-035", "AC-01", "SPEC-035")
@traces("REQ-035", "AC-02", "SPEC-035")
@traces("REQ-035", "AC-03", "SPEC-035")
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
        "assert 'Status: New file' in prompt; "
        "Path('tests/test_mode.py').write_text('MODE = 1\\n')\""
    )
    run_args = ["run", "--agent-command", worker_cmd]
    assert main([*run_args, "--root", str(tmp_path)]) == 0


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
        "AcceptanceCriteria and ImpactAnalysis" in " ".join(prompt_text.split())
    )
    assert "mt intent '<what to change and why>'" in generate_external_agents_guide()
    with pytest.raises(SystemExit):
        build_parser().parse_args(["intent", "--help"])
    intent_help = capsys.readouterr().out
    assert (
        "Intent statement describing what to change and why (or file path)."
        in intent_help
    )


@traces("REQ-045", "AC-02", "SPEC-045")
@traces("REQ-051", "AC-03", "SPEC-051")
def test_planner_single_concern_decomposition_contract(tmp_path: Path) -> None:
    """Verify planner decomposition contract requires single-concern test files."""
    from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
    from multi_tasker.orchestrator.prompt_context import (
        render_decomposition_contract,
    )

    lines = render_decomposition_contract("planner-agent", "TASK-010")
    joined = " ".join(lines)
    assert "single-concern" in joined
    assert "_and_" in joined
    assert "python3 -m py_compile <test_file>" in joined
    assert "pytest -q <test_file>" in joined
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    _write_document(
        tmp_path / "policy/traceability.yaml",
        "traceability_rules:\n"
        "  test_contract_verification_cmd: 'gcc -std=c89 -fsyntax-only <test_file>'\n"
        "  implementation_verification_cmd: './build/test_runner'\n",
    )
    custom, _ = build_agent_prompt(tmp_path, "planner-agent")
    assert "gcc -std=c89 -fsyntax-only <test_file>" in " ".join(custom.split())
    assert "./build/test_runner" in custom
