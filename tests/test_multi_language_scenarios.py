"""Mocked E2E pipeline TestContracts across Python, ANSI C, and Rust scenarios."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml

from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_artifacts_by_id, load_yaml_file
from multi_tasker.orchestrator.interaction_logger import record_task_event
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from multi_tasker.orchestrator.worktree import commit_traceable_change
from tests.test_multi_language_pipeline import (
    _C_FIXTURE,
    _PY_FIXTURE,
    _RUST_FIXTURE,
    LanguagePipelineFixture,
    _bootstrap_preset_pipeline_repo,
    _build_stage_artifacts,
    _write_file,
)

ALL_LANGUAGE_FIXTURES = (_PY_FIXTURE, _C_FIXTURE, _RUST_FIXTURE)
ALL_LANGUAGE_IDS = ("python", "ansi-c", "rust")


@dataclass(frozen=True)
class ScriptedTurn:
    """Scripted stage or worker response for a (role, target_id, attempt) key."""

    files: dict[str, str]
    expect_in_prompt: tuple[str, ...] = ()


@dataclass
class ScriptedPlan:
    """Mutable turn registry and invocation counter for a mocked pipeline run."""

    turns: dict[tuple[str, str, int], ScriptedTurn] = field(default_factory=dict)
    counts: dict[tuple[str, str], int] = field(default_factory=dict)


def configure_stage_gates(repository_root: Path, gates: dict[str, str]) -> None:
    """Update stage approval_gate values in artifact_lifecycle.yaml and commit."""
    pipeline_path = repository_root / "policy/artifact_lifecycle.yaml"
    pipeline = load_yaml_file(pipeline_path)
    for stage in pipeline.get("stages", []):
        stage_id = str(stage.get("id", ""))
        if stage_id in gates:
            stage["approval_gate"] = gates[stage_id]
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    commit_traceable_change(
        repository_root,
        ["policy/artifact_lifecycle.yaml"],
        "INT-001: Configure stage gates [traces: INT-001]",
    )


def _run_turn(
    worktree_path: Path,
    role: str,
    target_id: str,
    ctx: tuple[str, str, str],
    plan: ScriptedPlan,
) -> list[str]:
    """Verify prompt substrings, write scripted files, and log agent invocation."""
    attempt = plan.counts.get((role, target_id), 0) + 1
    plan.counts[(role, target_id)] = attempt
    turn = plan.turns[(role, target_id, attempt)]
    prompt_text, errors = build_agent_prompt(worktree_path, role, target_id)
    assert not errors, f"Prompt synthesis failed for {role} {target_id}: {errors}"
    for substring in turn.expect_in_prompt:
        assert substring in prompt_text, f"Missing {substring!r} in {role} prompt"
    for relative_path, content in turn.files.items():
        _write_file(worktree_path / relative_path, content)
    details = {"command": "mock", "return_code": 0, "duration_ms": 1}
    record_task_event(worktree_path, target_id, "agent_invocation", details, ctx, role)
    return list(turn.files.keys())


def install_scripted_plan(
    monkeypatch: pytest.MonkeyPatch, plan: ScriptedPlan
) -> ScriptedPlan:
    """Patch stage_runner and task_runner subprocess hooks with plan."""
    from multi_tasker.orchestrator import stage_runner, task_runner

    def _stage_hook(
        worktree_path: Path, role: str, doc: Any, ctx: tuple[str, str, str]
    ) -> list[str]:
        before = stage_runner._snapshot_artifacts(worktree_path)
        target_id = str(doc.frontmatter["id"])
        _run_turn(worktree_path, role, target_id, ctx, plan)
        return stage_runner._detect_stage_changes(worktree_path, before, target_id)

    def _worker_hook(
        worktree_path: Path, doc: Any, ctx: tuple[str, str, str], timeout: float = 300.0
    ) -> list[str]:
        _ = timeout
        task_id = str(doc.frontmatter["id"])
        return _run_turn(worktree_path, "worker-agent", task_id, ctx, plan)

    monkeypatch.setattr(stage_runner, "_run_stage_subprocess", _stage_hook)
    monkeypatch.setattr(task_runner, "_invoke_agent_in_worktree", _worker_hook)
    return plan


def rev_turn(
    rev_id: str, target_id: str, stage: str, verdict: str, finding: str = ""
) -> ScriptedTurn:
    """Build a ScriptedTurn writing artifacts/reviews/<rev_id>.md."""
    findings_yaml = f"findings:\n  - {finding}\n" if finding else "findings: []\n"
    text = (
        f"---\nid: {rev_id}\ntarget_artifacts: [{target_id}]\n"
        f"stage: {stage}\nverdict: {verdict}\n{findings_yaml}---\n"
    )
    return ScriptedTurn({f"artifacts/reviews/{rev_id}.md": text})


def esc_turn(esc_id: str, role: str, target_id: str, category: str) -> ScriptedTurn:
    """Build a ScriptedTurn writing artifacts/escalations/<esc_id>.md."""
    text = (
        f"---\nid: {esc_id}\nsource_agent: {role}\n"
        f"task_or_stage: {target_id}\naffected_artifacts: [{target_id}]\n"
        f"reason_category: {category}\nstatus: open\nresolved_by: null\n---\n"
        f"## Blocking Problem\nEscalated {target_id} due to {category}.\n"
    )
    return ScriptedTurn({f"artifacts/escalations/{esc_id}.md": text})


def expected_fence(preset: str) -> str:
    """Return expected Markdown code fence header for preset."""
    if preset == "ansi-c":
        return "```c"
    return "```rust" if preset == "rust" else "```python"


def build_base_turns(
    fixture: LanguagePipelineFixture, planned_tasks: bool = False
) -> dict[tuple[str, str, int], ScriptedTurn]:
    """Build standard 5-turn (REQ, SPEC, TASK1..2, worker 1..2) map for fixture."""
    docs = _build_stage_artifacts(fixture)
    task1, task2 = docs["TASK1"], docs["TASK2"]
    if planned_tasks:
        task1 = task1.replace("status: ready", "status: planned")
        task2 = task2.replace("status: ready", "status: planned")
    fence = expected_fence(fixture.preset)
    return {
        ("requirement-agent", "INT-001", 1): ScriptedTurn(
            {"artifacts/requirements/REQ-001.md": docs["REQ"]}
        ),
        ("specification-agent", "REQ-001", 1): ScriptedTurn(
            {"artifacts/specifications/SPEC-001.md": docs["SPEC"]}
        ),
        ("planner-agent", "SPEC-001", 1): ScriptedTurn(
            {"artifacts/tasks/TASK-001.md": task1, "artifacts/tasks/TASK-002.md": task2}
        ),
        ("worker-agent", "TASK-001", 1): ScriptedTurn(
            {fixture.test_path: fixture.test_source}, (fence,)
        ),
        ("worker-agent", "TASK-002", 1): ScriptedTurn(
            {fixture.impl_path: fixture.impl_source}, (fence, fixture.test_path)
        ),
    }


@traces("REQ-055", "AC-01", "SPEC-055")
@pytest.mark.parametrize("fixture", ALL_LANGUAGE_FIXTURES, ids=ALL_LANGUAGE_IDS)
def test_multi_language_production_gate_topology_e2e(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Verify human REQ gate, review-agent SPEC/TASK gates, and auto worker E2E."""
    _bootstrap_preset_pipeline_repo(tmp_path, fixture.preset)
    gates = {
        "intent_to_requirement": "human",
        "requirement_to_specification": "review-agent",
        "specification_to_tasks": "review-agent",
    }
    configure_stage_gates(tmp_path, gates)
    rev1 = rev_turn("REV-001", "SPEC-001", "specification", "pass")
    rev2 = rev_turn("REV-002", "TASK-001", "task_plan", "pass")
    rev3 = rev_turn("REV-003", "TASK-002", "task_plan", "pass")
    turns = {
        **build_base_turns(fixture, planned_tasks=True),
        ("review-agent", "SPEC-001", 1): rev1,
        ("review-agent", "TASK-001", 1): rev2,
        ("review-agent", "TASK-002", 1): rev3,
    }
    install_scripted_plan(monkeypatch, ScriptedPlan(turns=turns))
    capsys.readouterr()
    run_cmd = ["run", "--pipeline", "--agent-command", "mock", "--root", str(tmp_path)]
    assert main(run_cmd) == 0 and capsys.readouterr().out.strip() == "REQ-001"
    assert (
        load_artifacts_by_id(tmp_path)["REQ-001"].frontmatter["status"] == "in_review"
    )
    assert main(["approve", "REQ-001", "--root", str(tmp_path)]) == 0
    commit_traceable_change(
        tmp_path,
        ["artifacts/intents/INT-001.md", "artifacts/requirements/REQ-001.md"],
        "REQ-001: Approve requirement [traces: INT-001, REQ-001]",
    )
    capsys.readouterr()
    assert main(run_cmd) == 0
    done = set(capsys.readouterr().out.strip().splitlines())
    assert {"SPEC-001", "REV-001", "REV-002", "REV-003", "TASK-001", "TASK-002"} <= done
    assert main(["check", "all", "--root", str(tmp_path)]) == 0


def _verify_review_retry_recovery(
    retry_repo: Path, monkeypatch: pytest.MonkeyPatch, fixture: LanguagePipelineFixture
) -> None:
    """Verify SPEC and multi-task review rejection on cycle 1 recovers on cycle 2."""
    _bootstrap_preset_pipeline_repo(retry_repo, fixture.preset)
    gates = {
        "requirement_to_specification": "review-agent",
        "specification_to_tasks": "review-agent",
    }
    configure_stage_gates(retry_repo, gates)
    base = build_base_turns(fixture, planned_tasks=True)
    spec_f = base[("specification-agent", "REQ-001", 1)].files
    plan_f = base[("planner-agent", "SPEC-001", 1)].files
    turns = {
        **base,
        ("review-agent", "SPEC-001", 1): rev_turn(
            "REV-001", "SPEC-001", "specification", "fail", "Missing detail"
        ),
        ("specification-agent", "REQ-001", 2): ScriptedTurn(
            spec_f, ("### Artifact `REV-001`", "Missing detail")
        ),
        ("review-agent", "SPEC-001", 2): rev_turn(
            "REV-002", "SPEC-001", "specification", "pass"
        ),
        ("review-agent", "TASK-001", 1): rev_turn(
            "REV-003", "TASK-001", "task_plan", "pass"
        ),
        ("review-agent", "TASK-002", 1): rev_turn(
            "REV-004", "TASK-002", "task_plan", "fail", "Fix task scope"
        ),
        ("planner-agent", "SPEC-001", 2): ScriptedTurn(
            plan_f, ("### Artifact `REV-004`", "Fix task scope")
        ),
        ("review-agent", "TASK-001", 2): rev_turn(
            "REV-005", "TASK-001", "task_plan", "pass"
        ),
        ("review-agent", "TASK-002", 2): rev_turn(
            "REV-006", "TASK-002", "task_plan", "pass"
        ),
    }
    install_scripted_plan(monkeypatch, ScriptedPlan(turns=turns))
    run_cmd = [
        "run",
        "--pipeline",
        "--agent-command",
        "mock",
        "--root",
        str(retry_repo),
    ]
    assert main(run_cmd) == 0 and main(["check", "all", "--root", str(retry_repo)]) == 0


@traces("REQ-055", "AC-02", "SPEC-055")
@pytest.mark.parametrize("fixture", ALL_LANGUAGE_FIXTURES, ids=ALL_LANGUAGE_IDS)
def test_multi_language_review_retry_and_exhaustion_e2e(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Verify SPEC and multi-task review retry recovery and review exhaustion."""
    _verify_review_retry_recovery(tmp_path / "retry", monkeypatch, fixture)
    exhaust_repo = tmp_path / "exhaust"
    _bootstrap_preset_pipeline_repo(exhaust_repo, fixture.preset)
    configure_stage_gates(exhaust_repo, {"specification_to_tasks": "review-agent"})
    base = build_base_turns(fixture, planned_tasks=True)
    plan_f = base[("planner-agent", "SPEC-001", 1)].files
    turns = {
        **base,
        ("review-agent", "TASK-001", 1): rev_turn(
            "REV-001", "TASK-001", "task_plan", "fail", "Bad task 1"
        ),
        ("planner-agent", "SPEC-001", 2): ScriptedTurn(
            plan_f, ("### Artifact `REV-001`",)
        ),
        ("review-agent", "TASK-001", 2): rev_turn(
            "REV-002", "TASK-001", "task_plan", "fail", "Still bad"
        ),
    }
    install_scripted_plan(monkeypatch, ScriptedPlan(turns=turns))
    capsys.readouterr()
    run_cmd = [
        "run",
        "--pipeline",
        "--agent-command",
        "mock",
        "--root",
        str(exhaust_repo),
    ]
    assert main(run_cmd) == 1 and "[STAGE_REVIEW_EXHAUSTED]" in capsys.readouterr().out
    by_id = load_artifacts_by_id(exhaust_repo)
    assert by_id["ESC-001"].frontmatter["status"] == "awaiting_human"
    assert by_id["TASK-001"].frontmatter["status"] == "blocked"


@traces("REQ-055", "AC-03", "SPEC-055")
@pytest.mark.parametrize("fixture", ALL_LANGUAGE_FIXTURES, ids=ALL_LANGUAGE_IDS)
def test_multi_language_escalation_reroute_and_decision_resolution_e2e(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Verify infeasible_scope auto-reroute and ambiguity DEC resolution E2E."""
    _bootstrap_preset_pipeline_repo(tmp_path, fixture.preset)
    docs = _build_stage_artifacts(fixture)
    esc1 = esc_turn("ESC-001", "worker-agent", "TASK-001", "infeasible_scope")
    esc2 = esc_turn("ESC-002", "worker-agent", "TASK-002", "ambiguity")
    turns = {
        **build_base_turns(fixture),
        ("worker-agent", "TASK-001", 1): esc1,
        ("planner-agent", "ESC-001", 1): ScriptedTurn(
            {"artifacts/tasks/TASK-001.md": docs["TASK1"]},
            ("### Artifact `ESC-001`", "### Artifact `TASK-001`"),
        ),
        ("worker-agent", "TASK-001", 2): ScriptedTurn(
            {fixture.test_path: fixture.test_source}
        ),
        ("worker-agent", "TASK-002", 1): esc2,
        ("worker-agent", "TASK-002", 2): ScriptedTurn(
            {fixture.impl_path: fixture.impl_source}
        ),
    }
    install_scripted_plan(monkeypatch, ScriptedPlan(turns=turns))
    capsys.readouterr()
    run_cmd = ["run", "--pipeline", "--agent-command", "mock", "--root", str(tmp_path)]
    assert main(run_cmd) == 1 and "[GATE_TASK_ESCALATED]" in capsys.readouterr().out
    by_id = load_artifacts_by_id(tmp_path)
    assert by_id["ESC-001"].frontmatter["status"] == "resolved"
    assert by_id["TASK-002"].frontmatter["status"] == "blocked"
    _write_file(
        tmp_path / "artifacts/decisions/DEC-001.md",
        "---\nid: DEC-001\nresolves: ESC-002\napplies_to: [TASK-002]\n"
        "status: draft\n---\n## Resolution\nProceed with standard addition.\n",
    )
    assert main(["resolve", "ESC-002", "--by", "DEC-001", "--root", str(tmp_path)]) == 0
    assert load_artifacts_by_id(tmp_path)["TASK-002"].frontmatter["status"] == "ready"
    changed = [
        "artifacts/decisions/DEC-001.md",
        "artifacts/escalations/ESC-002.md",
        "artifacts/tasks/TASK-002.md",
    ]
    commit_traceable_change(
        tmp_path, changed, "DEC-001: Resolve ESC-002 [traces: ESC-002, DEC-001]"
    )
    assert main(run_cmd) == 0 and main(["check", "all", "--root", str(tmp_path)]) == 0
