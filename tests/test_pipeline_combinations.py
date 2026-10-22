"""Data-driven E2E pipeline combination TestContracts with mocked model calls."""

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


def _req_doc(status: str = "in_review") -> str:
    """Build a valid REQ-001 Markdown artifact string."""
    return (
        f"---\nid: REQ-001\ntitle: Calculation Service Requirement\n"
        f"status: {status}\ntraces_to: [INT-001]\ndecisions: []\n"
        "acceptance_criteria:\n"
        "  - id: AC-01\n    given: Input numbers\n"
        "    when: Added together\n    then: Returns sum\n"
        "version: 1\n---\n## Statement\nProvide addition helper.\n\n"
        "## Impact Analysis\nAdds src/domain/calc.py and tests/test_calc.py.\n"
    )


def _spec_doc(status: str = "in_review") -> str:
    """Build a valid SPEC-001 Markdown artifact string."""
    return (
        f"---\nid: SPEC-001\ntitle: Calculation Service Specification\n"
        f"status: {status}\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01]\ndecisions: []\n"
        "target_files:\n  tests: [tests/test_calc.py]\n"
        "  implementation: [src/domain/calc.py]\n---\n"
        "## Design Overview\nImplement add_values in src/domain/calc.py.\n\n"
        "## Public Interfaces\ndef add_values(left: int, right: int) -> int\n\n"
        "## Test Contract Mapping\n- REQ-001:AC-01 -> tests/test_calc.py\n"
    )


def _task_one_doc(status: str = "ready") -> str:
    """Build a valid test_contract TASK-001 Markdown artifact string."""
    return (
        f"---\nid: TASK-001\ntitle: Add Calculation TestContract\n"
        f"type: test_contract\nstatus: {status}\n"
        "traces_to: [REQ-001, SPEC-001]\ndepends_on: []\n"
        "required_files: []\nwrite_files: [tests/test_calc.py]\n"
        "verification_cmd: python3 -m py_compile tests/test_calc.py\n---\n"
        "## Objective\nWrite test_calc.py.\n\n"
        "## Scoped Instructions\nDecorate test_add_values with @traces.\n"
    )


def _task_two_doc(status: str = "ready") -> str:
    """Build a valid implementation TASK-002 Markdown artifact string."""
    return (
        f"---\nid: TASK-002\ntitle: Implement Calculation Module\n"
        f"type: implementation\nstatus: {status}\n"
        "traces_to: [REQ-001, SPEC-001]\ndepends_on: [TASK-001]\n"
        "required_files: [tests/test_calc.py]\n"
        "write_files: [src/domain/calc.py]\n"
        "verification_cmd: pytest -q tests/test_calc.py\n---\n"
        "## Objective\nImplement add_values.\n\n"
        "## Scoped Instructions\nCreate src/domain/calc.py.\n"
    )


def _rev_doc(rev_id: str, target_id: str, stage: str, verdict: str) -> str:
    """Build a valid REV Markdown artifact string."""
    finding = "  - Missing edge case coverage in specification\n"
    findings_block = f"findings:\n{finding}" if verdict == "fail" else "findings: []\n"
    return (
        f"---\nid: {rev_id}\ntarget_artifacts: [{target_id}]\n"
        f"stage: {stage}\nverdict: {verdict}\n{findings_block}---\n"
    )


def _esc_doc(esc_id: str, role: str, target_id: str, category: str) -> str:
    """Build a valid ESC Markdown artifact string."""
    return (
        f"---\nid: {esc_id}\nsource_agent: {role}\n"
        f"task_or_stage: {target_id}\naffected_artifacts: [{target_id}]\n"
        f"reason_category: {category}\nstatus: open\nresolved_by: null\n---\n"
        "## Blocking Problem\nScope requires task decomposition adjustment.\n"
    )


_TEST_FILE_CODE = (
    '"""TestContract for calculation module."""\n\n'
    "from multi_tasker.domain.models import traces\n"
    "from src.domain.calc import add_values\n\n\n"
    '@traces("REQ-001", "AC-01", "SPEC-001")\n'
    "def test_add_values() -> None:\n"
    '    """Verify add_values returns sum."""\n'
    "    assert add_values(2, 3) == 5\n"
)

_IMPL_FILE_CODE = (
    '"""Calculation domain module."""\n\n\n'
    "def add_values(left: int, right: int) -> int:\n"
    '    """Return sum of left and right integers."""\n'
    "    return left + right\n"
)

_BASE_TURNS: tuple[MockTurn, ...] = (
    MockTurn(
        "requirement-agent",
        "INT-001",
        1,
        ("Requirement Decomposition Contract", "### Artifact `INT-001`"),
        {"artifacts/requirements/REQ-001.md": _req_doc()},
    ),
    MockTurn(
        "specification-agent",
        "REQ-001",
        1,
        ("### Artifact `REQ-001`",),
        {"artifacts/specifications/SPEC-001.md": _spec_doc()},
    ),
    MockTurn(
        "planner-agent",
        "SPEC-001",
        1,
        ("Planner Decomposition Contract", "### Artifact `SPEC-001`"),
        {
            "artifacts/tasks/TASK-001.md": _task_one_doc(),
            "artifacts/tasks/TASK-002.md": _task_two_doc(),
        },
    ),
    MockTurn(
        "worker-agent",
        "TASK-001",
        1,
        ("### Artifact `TASK-001`", "### Write File `tests/test_calc.py`"),
        {"tests/test_calc.py": _TEST_FILE_CODE},
    ),
    MockTurn(
        "worker-agent",
        "TASK-002",
        1,
        ("### Artifact `TASK-002`", "### Required File `tests/test_calc.py`"),
        {"src/domain/calc.py": _IMPL_FILE_CODE},
    ),
)

_AUTO_GATES = {
    "intent_to_requirement": "auto",
    "requirement_to_specification": "auto",
    "specification_to_tasks": "auto",
    "execute_tasks": "auto",
}
_REV_SPEC_GATES = {**_AUTO_GATES, "requirement_to_specification": "review-agent"}
_HUMAN_REQ_GATES = {**_AUTO_GATES, "intent_to_requirement": "human"}

_REV_FAIL_TURN = MockTurn(
    "review-agent",
    "SPEC-001",
    1,
    ("Semantic Review Rubric", "### Artifact `SPEC-001`"),
    {
        "artifacts/reviews/REV-001.md": _rev_doc(
            "REV-001", "SPEC-001", "specification", "fail"
        )
    },
)
_SPEC_RETRY_TURN = MockTurn(
    "specification-agent",
    "REQ-001",
    2,
    ("### Artifact `REV-001`", "Missing edge case coverage in specification"),
    {"artifacts/specifications/SPEC-001.md": _spec_doc()},
)
_WORKER_ESC_ONE = MockTurn(
    "worker-agent",
    "TASK-001",
    1,
    ("### Artifact `TASK-001`",),
    {
        "artifacts/escalations/ESC-001.md": _esc_doc(
            "ESC-001", "worker-agent", "TASK-001", "infeasible_scope"
        )
    },
)
_PLANNER_RESCOPE = MockTurn(
    "planner-agent",
    "ESC-001",
    1,
    ("### Artifact `ESC-001`", "### Artifact `TASK-001`"),
    {"artifacts/tasks/TASK-001.md": _task_one_doc("ready")},
)

PIPELINE_SCENARIOS: tuple[PipelineScenario, ...] = (
    PipelineScenario(
        "all_auto_gates_e2e_success",
        _AUTO_GATES,
        _BASE_TURNS,
        0,
        ("REQ-001", "SPEC-001", "TASK-001", "TASK-002"),
        (),
        {
            "INT-001": "processed",
            "REQ-001": "approved",
            "SPEC-001": "approved",
            "TASK-001": "done",
            "TASK-002": "done",
        },
    ),
    PipelineScenario(
        "human_gate_pauses_after_requirement_stage",
        _HUMAN_REQ_GATES,
        (_BASE_TURNS[0],),
        0,
        ("REQ-001",),
        (),
        {"INT-001": "open", "REQ-001": "in_review"},
    ),
    PipelineScenario(
        "review_reject_cycle_1_recovers_on_cycle_2_with_inlined_feedback",
        _REV_SPEC_GATES,
        (
            *_BASE_TURNS,
            _REV_FAIL_TURN,
            _SPEC_RETRY_TURN,
            MockTurn(
                "review-agent",
                "SPEC-001",
                2,
                ("### Artifact `SPEC-001`",),
                {
                    "artifacts/reviews/REV-001.md": _rev_doc(
                        "REV-001", "SPEC-001", "specification", "pass"
                    )
                },
            ),
        ),
        0,
        ("REQ-001", "SPEC-001", "REV-002", "TASK-001", "TASK-002"),
        (),
        {
            "INT-001": "processed",
            "REQ-001": "approved",
            "SPEC-001": "approved",
            "TASK-001": "done",
            "TASK-002": "done",
        },
    ),
    PipelineScenario(
        "review_reject_reaches_max_cycles_and_emits_review_exhausted_esc",
        _REV_SPEC_GATES,
        (
            _BASE_TURNS[0],
            _BASE_TURNS[1],
            _REV_FAIL_TURN,
            _SPEC_RETRY_TURN,
            MockTurn(
                "review-agent",
                "SPEC-001",
                2,
                ("### Artifact `SPEC-001`",),
                {
                    "artifacts/reviews/REV-001.md": _rev_doc(
                        "REV-001", "SPEC-001", "specification", "fail"
                    )
                },
            ),
        ),
        1,
        (),
        ("STAGE_REVIEW_EXHAUSTED",),
        {"REQ-001": "approved", "SPEC-001": "blocked", "ESC-001": "awaiting_human"},
    ),
    PipelineScenario(
        "worker_infeasible_scope_auto_reroutes_to_planner_and_completes",
        _AUTO_GATES,
        (
            *_BASE_TURNS[:3],
            _WORKER_ESC_ONE,
            _PLANNER_RESCOPE,
            MockTurn(
                "worker-agent",
                "TASK-001",
                2,
                ("### Artifact `TASK-001`",),
                {"tests/test_calc.py": _TEST_FILE_CODE},
            ),
            _BASE_TURNS[4],
        ),
        0,
        ("REQ-001", "SPEC-001", "ESC-001", "TASK-001", "TASK-002"),
        (),
        {"ESC-001": "resolved", "TASK-001": "done", "TASK-002": "done"},
    ),
    PipelineScenario(
        "worker_reroute_cap_exceeded_routes_second_escalation_to_human",
        _AUTO_GATES,
        (
            *_BASE_TURNS[:3],
            _WORKER_ESC_ONE,
            _PLANNER_RESCOPE,
            MockTurn(
                "worker-agent",
                "TASK-001",
                2,
                (),
                {
                    "artifacts/escalations/ESC-002.md": _esc_doc(
                        "ESC-002", "worker-agent", "TASK-001", "infeasible_scope"
                    )
                },
            ),
        ),
        1,
        (),
        ("GATE_TASK_ESCALATED",),
        {"ESC-001": "resolved", "ESC-002": "awaiting_human", "TASK-001": "blocked"},
    ),
    PipelineScenario(
        "merge_gate_locked_test_contract_violation_preserves_base_branch",
        _AUTO_GATES,
        (
            *_BASE_TURNS[:4],
            MockTurn(
                "worker-agent",
                "TASK-002",
                1,
                (),
                {"tests/test_calc.py": "# tampered test\n"},
            ),
        ),
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
    from tests.test_task_runner import _git_commit_all

    _git_commit_all(
        repository_root, "INT-001: Configure scenario pipeline [traces: INT-001]"
    )


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
