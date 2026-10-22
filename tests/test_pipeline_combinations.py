"""Data-driven E2E pipeline combination TestContracts with mocked model calls."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_artifacts_by_id, load_yaml_file
from multi_tasker.orchestrator.interaction_logger import record_task_event
from multi_tasker.orchestrator.lifecycle import bootstrap_evaluation_repository
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from multi_tasker.orchestrator.worktree import commit_traceable_change


@dataclass(frozen=True)
class MockTurn:
    """Scripted model response for a specific (role, target_id, attempt) tuple."""

    role: str
    target_id: str
    attempt: int = 1
    expect_in_prompt: tuple[str, ...] = ()
    write_files: dict[str, str] = field(default_factory=dict)
    return_code: int = 0


@dataclass(frozen=True)
class PipelineScenario:
    """Declarative E2E pipeline combination test specification."""

    name: str
    stage_gates: dict[str, str]
    turns: tuple[MockTurn, ...]
    expected_exit_code: int
    expected_completed: tuple[str, ...]
    expected_rules: tuple[str, ...]
    expected_states: dict[str, str]


_REQ_MD = (
    "---\nid: REQ-001\ntitle: Calculation Service Requirement\n"
    "status: in_review\ntraces_to: [INT-001]\ndecisions: []\n"
    "acceptance_criteria:\n  - id: AC-01\n    given: Input numbers\n"
    "    when: Added together\n    then: Returns sum\n"
    "version: 1\n---\n## Statement\nProvide addition helper.\n\n"
    "## Impact Analysis\nAdds src/domain/calc.py and tests/test_calc.py.\n"
)

_SPEC_MD = (
    "---\nid: SPEC-001\ntitle: Calculation Service Specification\n"
    "status: in_review\ntraces_to: [REQ-001]\n"
    "covers_criteria: [REQ-001:AC-01]\ndecisions: []\n"
    "target_files:\n  tests: [tests/test_calc.py]\n"
    "  implementation: [src/domain/calc.py]\n---\n"
    "## Design Overview\nImplement add_values in src/domain/calc.py.\n\n"
    "## Public Interfaces\ndef add_values(left: int, right: int) -> int\n\n"
    "## Test Contract Mapping\n- REQ-001:AC-01 -> tests/test_calc.py\n"
)


def _task_md(task_id: str, is_impl: bool = False) -> str:
    """Build a valid test_contract or implementation TASK Markdown string."""
    kind = "implementation" if is_impl else "test_contract"
    deps = "[TASK-001]" if is_impl else "[]"
    req_f = "[tests/test_calc.py]" if is_impl else "[]"
    out_f = "src/domain/calc.py" if is_impl else "tests/test_calc.py"
    cmd = (
        "pytest -q tests/test_calc.py"
        if is_impl
        else "python3 -m py_compile tests/test_calc.py"
    )
    return (
        f"---\nid: {task_id}\ntitle: Task {task_id} Calculation Work\n"
        f"type: {kind}\nstatus: ready\ntraces_to: [REQ-001, SPEC-001]\n"
        f"depends_on: {deps}\nrequired_files: {req_f}\n"
        f"write_files: [{out_f}]\nverification_cmd: {cmd}\n---\n"
        f"## Objective\nRun {task_id}.\n\n## Scoped Instructions\nWrite {out_f}.\n"
    )


def _rev_md(verdict: str) -> str:
    """Build a valid REV-001 Markdown artifact string for SPEC-001."""
    finding = "  - Missing edge case coverage in specification\n"
    block = f"findings:\n{finding}" if verdict == "fail" else "findings: []\n"
    return (
        f"---\nid: REV-001\ntarget_artifacts: [SPEC-001]\n"
        f"stage: specification\nverdict: {verdict}\n{block}---\n"
    )


def _esc_md(esc_id: str) -> str:
    """Build a valid worker-agent infeasible_scope ESC Markdown string."""
    return (
        f"---\nid: {esc_id}\nsource_agent: worker-agent\n"
        "task_or_stage: TASK-001\naffected_artifacts: [TASK-001]\n"
        "reason_category: infeasible_scope\nstatus: open\nresolved_by: null\n---\n"
        "## Blocking Problem\nScope requires task decomposition adjustment.\n"
    )


_TEST_PY = (
    '"""TestContract for calculation module."""\n\n'
    "from multi_tasker.domain.models import traces\n"
    "from src.domain.calc import add_values\n\n\n"
    '@traces("REQ-001", "AC-01", "SPEC-001")\n'
    "def test_add_values() -> None:\n"
    '    """Verify add_values returns sum."""\n'
    "    assert add_values(2, 3) == 5\n"
)

_IMPL_PY = (
    '"""Calculation domain module."""\n\n\n'
    "def add_values(left: int, right: int) -> int:\n"
    '    """Return sum of left and right integers."""\n'
    "    return left + right\n"
)

_PATHS = (
    "artifacts/requirements/REQ-001.md",
    "artifacts/specifications/SPEC-001.md",
    "artifacts/reviews/REV-001.md",
    "artifacts/tasks/TASK-001.md",
    "artifacts/tasks/TASK-002.md",
    "artifacts/escalations/ESC-001.md",
    "artifacts/escalations/ESC-002.md",
)
_REQ_PATH, _SPEC_PATH, _REV_PATH, _TASK1_PATH, _TASK2_PATH, _ESC1_PATH, _ESC2_PATH = (
    _PATHS
)
_P_REQ = ("Requirement Decomposition Contract", "### Artifact `INT-001`")
_P_PLAN = ("Planner Decomposition Contract", "### Artifact `SPEC-001`")
_P_WORK1 = ("### Artifact `TASK-001`", "### Write File `tests/test_calc.py`")
_P_WORK2 = ("### Artifact `TASK-002`", "### Required File `tests/test_calc.py`")
_P_SPEC2 = ("### Artifact `REV-001`", "Missing edge case coverage in specification")
_P_RESC = ("### Artifact `ESC-001`", "### Artifact `TASK-001`")
_P_SPEC1 = ("### Artifact `REQ-001`",)
_P_REV1 = ("Semantic Review Rubric",)
_PLAN_OUT = {
    _TASK1_PATH: _task_md("TASK-001", False),
    _TASK2_PATH: _task_md("TASK-002", True),
}

_T_REQ = MockTurn("requirement-agent", "INT-001", 1, _P_REQ, {_REQ_PATH: _REQ_MD})
_T_SPEC = MockTurn(
    "specification-agent", "REQ-001", 1, _P_SPEC1, {_SPEC_PATH: _SPEC_MD}
)
_T_PLAN = MockTurn("planner-agent", "SPEC-001", 1, _P_PLAN, _PLAN_OUT)
_T_WORK1 = MockTurn(
    "worker-agent", "TASK-001", 1, _P_WORK1, {"tests/test_calc.py": _TEST_PY}
)
_T_WORK2 = MockTurn(
    "worker-agent", "TASK-002", 1, _P_WORK2, {"src/domain/calc.py": _IMPL_PY}
)
_BASE = (_T_REQ, _T_SPEC, _T_PLAN, _T_WORK1, _T_WORK2)
_T_REV_F1 = MockTurn(
    "review-agent", "SPEC-001", 1, _P_REV1, {_REV_PATH: _rev_md("fail")}
)
_T_REV_P2 = MockTurn("review-agent", "SPEC-001", 2, (), {_REV_PATH: _rev_md("pass")})
_T_REV_F2 = MockTurn("review-agent", "SPEC-001", 2, (), {_REV_PATH: _rev_md("fail")})
_T_SPEC_2 = MockTurn(
    "specification-agent", "REQ-001", 2, _P_SPEC2, {_SPEC_PATH: _SPEC_MD}
)
_T_ESC1 = MockTurn("worker-agent", "TASK-001", 1, (), {_ESC1_PATH: _esc_md("ESC-001")})
_T_ESC2 = MockTurn("worker-agent", "TASK-001", 2, (), {_ESC2_PATH: _esc_md("ESC-002")})
_T_RESCOPE = MockTurn(
    "planner-agent", "ESC-001", 1, _P_RESC, {_TASK1_PATH: _PLAN_OUT[_TASK1_PATH]}
)
_T_WORK1_2 = MockTurn(
    "worker-agent", "TASK-001", 2, (), {"tests/test_calc.py": _TEST_PY}
)
_T_TAMPER = MockTurn(
    "worker-agent", "TASK-002", 1, (), {"tests/test_calc.py": "# tampered\n"}
)

_AUTO = {
    "intent_to_requirement": "auto",
    "requirement_to_specification": "auto",
    "specification_to_tasks": "auto",
    "execute_tasks": "auto",
}
_REV_SPEC = {**_AUTO, "requirement_to_specification": "review-agent"}
_HUMAN_REQ = {**_AUTO, "intent_to_requirement": "human"}
_ALL_DONE = {
    "INT-001": "processed",
    "REQ-001": "approved",
    "SPEC-001": "approved",
    "TASK-001": "done",
    "TASK-002": "done",
}

PIPELINE_SCENARIOS: tuple[PipelineScenario, ...] = (
    PipelineScenario(
        "all_auto_gates_e2e_success",
        _AUTO,
        _BASE,
        0,
        ("REQ-001", "SPEC-001", "TASK-001", "TASK-002"),
        (),
        _ALL_DONE,
    ),
    PipelineScenario(
        "human_gate_pauses_after_requirement_stage",
        _HUMAN_REQ,
        (_T_REQ,),
        0,
        ("REQ-001",),
        (),
        {"INT-001": "open", "REQ-001": "in_review"},
    ),
    PipelineScenario(
        "review_reject_cycle_1_recovers_on_cycle_2_with_inlined_feedback",
        _REV_SPEC,
        (*_BASE, _T_REV_F1, _T_SPEC_2, _T_REV_P2),
        0,
        ("REQ-001", "SPEC-001", "REV-002", "TASK-001", "TASK-002"),
        (),
        _ALL_DONE,
    ),
    PipelineScenario(
        "review_reject_reaches_max_cycles_and_emits_review_exhausted_esc",
        _REV_SPEC,
        (_T_REQ, _T_SPEC, _T_REV_F1, _T_SPEC_2, _T_REV_F2),
        1,
        (),
        ("STAGE_REVIEW_EXHAUSTED",),
        {"REQ-001": "approved", "SPEC-001": "blocked", "ESC-001": "awaiting_human"},
    ),
    PipelineScenario(
        "worker_infeasible_scope_auto_reroutes_to_planner_and_completes",
        _AUTO,
        (*_BASE[:3], _T_ESC1, _T_RESCOPE, _T_WORK1_2, _T_WORK2),
        0,
        ("REQ-001", "SPEC-001", "ESC-001", "TASK-001", "TASK-002"),
        (),
        {"ESC-001": "resolved", "TASK-001": "done", "TASK-002": "done"},
    ),
    PipelineScenario(
        "worker_reroute_cap_exceeded_routes_second_escalation_to_human",
        _AUTO,
        (*_BASE[:3], _T_ESC1, _T_RESCOPE, _T_ESC2),
        1,
        (),
        ("GATE_TASK_ESCALATED",),
        {"ESC-001": "resolved", "ESC-002": "awaiting_human", "TASK-001": "blocked"},
    ),
    PipelineScenario(
        "merge_gate_locked_test_contract_violation_preserves_base_branch",
        _AUTO,
        (*_BASE[:4], _T_TAMPER),
        1,
        (),
        ("PERM_LOCKED_TEST_CONTRACT", "PERM_OUTSIDE_WRITE_SCOPE"),
        {"TASK-001": "done", "TASK-002": "ready"},
    ),
)


def _configure_scenario_repository(
    repository_root: Path, scenario: PipelineScenario
) -> None:
    """Bootstrap repo and apply scenario stage_gates."""
    bootstrap_evaluation_repository(repository_root, "Build calculation service.")
    pipeline_path = repository_root / "policy" / "pipeline.yaml"
    pipeline = load_yaml_file(pipeline_path)
    for stage in pipeline.get("stages", []):
        stage_id = str(stage.get("id", ""))
        if stage_id in scenario.stage_gates:
            stage["approval_gate"] = scenario.stage_gates[stage_id]
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    msg = "INT-001: Configure scenario pipeline [traces: INT-001]"
    commit_traceable_change(repository_root, ["policy/pipeline.yaml"], msg)


def _execute_scripted_turn(
    worktree_path: Path,
    role: str,
    target_id: str,
    ctx: tuple[str, str, str],
    turn_map: dict[tuple[str, str, int], MockTurn],
    call_counts: dict[tuple[str, str], int],
) -> list[str]:
    """Verify prompt expectations, write scripted files, and log agent invocation."""
    attempt = call_counts.get((role, target_id), 0) + 1
    call_counts[(role, target_id)] = attempt
    turn = turn_map[(role, target_id, attempt)]
    prompt_text, errors = build_agent_prompt(worktree_path, role, target_id)
    assert not errors, f"Prompt errors for {role} {target_id}: {errors}"
    for expected_sub in turn.expect_in_prompt:
        assert expected_sub in prompt_text, f"Missing {expected_sub!r} in prompt"
    for rel_path, content in turn.write_files.items():
        target_file = worktree_path / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(content, encoding="utf-8")
    details = {"command": "mock", "return_code": turn.return_code, "duration_ms": 1}
    record_task_event(worktree_path, target_id, "agent_invocation", details, ctx, role)
    return list(turn.write_files.keys())


def _install_mock_model_dispatcher(
    monkeypatch: pytest.MonkeyPatch, scenario: PipelineScenario
) -> dict[tuple[str, str], int]:
    """Patch stage and worker subprocess hooks with scenario turn lookup."""
    from multi_tasker.orchestrator import stage_runner, task_runner

    turn_map = {
        (turn.role, turn.target_id, turn.attempt): turn for turn in scenario.turns
    }
    counts: dict[tuple[str, str], int] = {}

    def _mock_stage_sub(
        worktree_path: Path, role: str, doc: Any, ctx: tuple[str, str, str]
    ) -> list[str]:
        before = stage_runner._snapshot_artifacts(worktree_path)
        target_id = str(doc.frontmatter["id"])
        _execute_scripted_turn(worktree_path, role, target_id, ctx, turn_map, counts)
        return stage_runner._detect_stage_changes(worktree_path, before, target_id)

    def _mock_worker_sub(
        worktree_path: Path, doc: Any, ctx: tuple[str, str, str], timeout: float = 300.0
    ) -> list[str]:
        _ = timeout
        tid = str(doc.frontmatter["id"])
        return _execute_scripted_turn(
            worktree_path, "worker-agent", tid, ctx, turn_map, counts
        )

    monkeypatch.setattr(stage_runner, "_run_stage_subprocess", _mock_stage_sub)
    monkeypatch.setattr(task_runner, "_invoke_agent_in_worktree", _mock_worker_sub)
    return counts


@traces("REQ-046", "AC-01", "SPEC-046")
@traces("REQ-046", "AC-02", "SPEC-046")
@traces("REQ-046", "AC-03", "SPEC-046")
@pytest.mark.parametrize(
    "scenario", PIPELINE_SCENARIOS, ids=[item.name for item in PIPELINE_SCENARIOS]
)
def test_declarative_pipeline_combinations_matrix(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    scenario: PipelineScenario,
) -> None:
    """Verify full declarative pipeline combinations with mocked model turns."""
    _configure_scenario_repository(tmp_path, scenario)
    call_counts = _install_mock_model_dispatcher(monkeypatch, scenario)
    capsys.readouterr()
    run_args = ["run", "--pipeline", "--agent-command", "mock", "--root", str(tmp_path)]
    exit_code = main(run_args)
    output_text = capsys.readouterr().out.strip()
    assert exit_code == scenario.expected_exit_code, f"Unexpected output: {output_text}"
    assert call_counts
    if scenario.expected_exit_code == 0:
        completed = output_text.splitlines()
        for artifact_id in scenario.expected_completed:
            assert artifact_id in completed
        if "TASK-002" in scenario.expected_completed:
            assert main(["check", "all", "--root", str(tmp_path)]) == 0
    else:
        for rule_id in scenario.expected_rules:
            assert f"[{rule_id}]" in output_text
    by_id = load_artifacts_by_id(tmp_path)
    for artifact_id, expected_state in scenario.expected_states.items():
        assert artifact_id in by_id, f"Missing expected artifact {artifact_id}"
        assert by_id[artifact_id].frontmatter.get("status") == expected_state


@traces("REQ-047", "AC-01", "SPEC-047")
@traces("REQ-047", "AC-02", "SPEC-047")
@traces("REQ-047", "AC-03", "SPEC-047")
def test_worktree_pythonpath_precedence_and_identical_review_retry(
    tmp_path: Path,
) -> None:
    """Verify worktree/src PYTHONPATH precedence, identical REV diff, and empty diff."""
    from multi_tasker.orchestrator import merge_gate, prompt_builder, stage_runner

    bootstrap_evaluation_repository(tmp_path, "Verify worktree PYTHONPATH.")
    int_doc = load_artifacts_by_id(tmp_path)["INT-001"]
    expected = f"{tmp_path / 'src'}{os.pathsep}{tmp_path}"
    ctx = ("echo", "agy", "m")
    _, _, s_env = stage_runner._prepare_stage_invocation(
        tmp_path, "requirement-agent", int_doc, ctx
    )
    _, w_env = prompt_builder.prepare_worker_invocation(
        tmp_path, int_doc, tmp_path / ".mt_prompt.md", ctx
    )
    assert s_env["PYTHONPATH"] == expected and w_env["PYTHONPATH"] == expected
    before_empty = stage_runner._snapshot_artifacts(tmp_path)
    assert stage_runner._detect_stage_changes(tmp_path, before_empty, "INT-001") == []
    (tmp_path / "src/domain").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src/domain/mod.py").write_text("VAL = 7\n", encoding="utf-8")
    cmd = "python3 -c 'import domain.mod; assert domain.mod.VAL == 7'"
    assert merge_gate._run_verification_command(tmp_path, cmd) == []
