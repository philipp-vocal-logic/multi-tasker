"""Mocked E2E pipeline TestContracts for parallel layers, faults, and supersession."""

from pathlib import Path

import pytest

from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_artifacts_by_id
from multi_tasker.orchestrator.lineage import trace_lineage
from multi_tasker.orchestrator.worktree import commit_traceable_change
from tests.test_multi_language_pipeline import (
    LanguagePipelineFixture,
    _bootstrap_preset_pipeline_repo,
    _build_stage_artifacts,
)
from tests.test_multi_language_scenarios import (
    ALL_LANGUAGE_FIXTURES,
    ALL_LANGUAGE_IDS,
    ScriptedPlan,
    ScriptedTurn,
    build_base_turns,
    expected_fence,
    install_scripted_plan,
)

_SERVICE_FIXTURES: dict[str, tuple[str, str, str, str, str, str, str]] = {
    "ansi-c": (
        "tests/test_scorer.c",
        "src/services/scorer.c",
        (
            "gcc -std=c89 -pedantic -Wall -Wextra -Werror "
            "-fsyntax-only tests/test_scorer.c"
        ),
        (
            'sh -c "gcc -std=c89 -pedantic -Wall -Wextra -Werror '
            'tests/test_scorer.c src/services/scorer.c -o .report/t_sc && .report/t_sc"'
        ),
        (
            "/** TestContract for ANSI C scorer. */\n#include <assert.h>\n\n"
            "int scale_score(int score);\n\n"
            '/* @traces("REQ-001", "AC-01", "SPEC-001") */\n'
            "void test_scale_score(void) {\n    assert(scale_score(4) == 8);\n}\n\n"
            "int main(void) {\n    test_scale_score();\n    return 0;\n}\n"
        ),
        (
            "/** C scorer service. */\n"
            "int scale_score(int score) {\n    return score * 2;\n}\n"
        ),
        (
            '/** Bad C. */\n#include "cli/app.h"\n'
            'int bad_fn(int val) {\n    printf("%d", val);\n    return val;\n}\n'
        ),
    ),
    "rust": (
        "tests/test_scorer.rs",
        "src/services/scorer.rs",
        (
            "rustfmt --check --edition 2021 "
            "--config skip_children=true tests/test_scorer.rs"
        ),
        (
            'sh -c "rustc --edition 2021 --test tests/test_scorer.rs '
            '-o .report/t_sc && .report/t_sc --quiet"'
        ),
        (
            "//! TestContract for Rust scorer.\n\n"
            '#[path = "../src/services/scorer.rs"]\nmod scorer;\n\n'
            '// @traces("REQ-001", "AC-01", "SPEC-001")\n#[test]\n'
            "fn test_scale_score() {\n    assert_eq!(scorer::scale_score(4), 8);\n}\n"
        ),
        (
            "//! Rust scorer service.\n"
            "pub fn scale_score(score: i32) -> i32 {\n    score * 2\n}\n"
        ),
        (
            "//! Bad Rust.\nuse crate::cli::app;\n"
            'pub fn bad_fn(val: i32) -> i32 {\n    println!("{}", val);\n    val\n}\n'
        ),
    ),
    "python": (
        "tests/test_scorer.py",
        "src/services/scorer.py",
        "python3 -m py_compile tests/test_scorer.py",
        "pytest -q tests/test_scorer.py",
        (
            '"""TestContract for Python scorer."""\n\n'
            "from multi_tasker.domain.models import traces\n"
            "from src.services.scorer import scale_score\n\n\n"
            '@traces("REQ-001", "AC-01", "SPEC-001")\n'
            "def test_scale_score() -> None:\n"
            '    """Verify scale_score doubles input."""\n'
            "    assert scale_score(4) == 8\n"
        ),
        (
            '"""Python scorer service."""\n\n\n'
            "def scale_score(score: int) -> int:\n"
            '    """Return doubled score."""\n'
            "    return score * 2\n"
        ),
        (
            '"""Bad Python."""\n\nimport src.cli.app\n\n\n'
            "def bad_fn(val: int) -> int:\n"
            '    """Violates print and layer import."""\n'
            "    print(val)\n"
            "    return val\n"
        ),
    ),
}


def _parallel_spec_and_tasks(
    fixture: LanguagePipelineFixture, docs: dict[str, str]
) -> tuple[str, dict[str, str]]:
    """Build SPEC-001 and TASK-001..004 Markdown texts for parallel layers."""
    s_test, s_impl, s_tcmd, s_icmd, _, _, _ = _SERVICE_FIXTURES[fixture.preset]
    spec_md = (
        "---\nid: SPEC-001\ntitle: Multi-Layer Calculation and Scorer Specification\n"
        "status: in_review\ntraces_to: [REQ-001]\ncovers_criteria: [REQ-001:AC-01]\n"
        f"decisions: []\ntarget_files:\n  tests: [{fixture.test_path}, {s_test}]\n"
        f"  implementation: [{fixture.impl_path}, {s_impl}]\n---\n"
        "## Design Overview\nDomain and service modules.\n\n"
        "## Public Interfaces\nadd_values and scale_score\n\n"
        f"## Test Contract Mapping\n- REQ-001:AC-01 -> {fixture.test_path}, {s_test}\n"
    )
    task2_md = (
        "---\nid: TASK-002\ntitle: Author Scorer TestContract\ntype: test_contract\n"
        "status: ready\ntraces_to: [REQ-001, SPEC-001]\ndepends_on: []\n"
        f"required_files: []\nwrite_files: [{s_test}]\nverification_cmd: '{s_tcmd}'\n"
        "---\n## Objective\nWrite test.\n\n## Scoped Instructions\nCreate test.\n"
    )
    task4_md = (
        "---\nid: TASK-004\ntitle: Implement Scorer Service\ntype: implementation\n"
        "status: ready\ntraces_to: [REQ-001, SPEC-001]\ndepends_on: [TASK-002]\n"
        f"required_files: [{s_test}]\nwrite_files: [{s_impl}]\n"
        f"verification_cmd: '{s_icmd}'\n---\n"
        "## Objective\nWrite service.\n\n## Scoped Instructions\nCreate service.\n"
    )
    tasks = {
        "artifacts/tasks/TASK-001.md": docs["TASK1"],
        "artifacts/tasks/TASK-002.md": task2_md,
        "artifacts/tasks/TASK-003.md": docs["TASK2"].replace("TASK-002", "TASK-003"),
        "artifacts/tasks/TASK-004.md": task4_md,
    }
    return spec_md, tasks


def _build_parallel_wave_plan(fixture: LanguagePipelineFixture) -> ScriptedPlan:
    """Build 4-task parallel wave plan with fault attempts on TASK-003."""
    docs = _build_stage_artifacts(fixture)
    s_test, s_impl, _, _, s_tsrc, s_isrc, bad_src = _SERVICE_FIXTURES[fixture.preset]
    spec_md, plan_files = _parallel_spec_and_tasks(fixture, docs)
    return ScriptedPlan(
        turns={
            ("requirement-agent", "INT-001", 1): ScriptedTurn(
                {"artifacts/requirements/REQ-001.md": docs["REQ"]}
            ),
            ("specification-agent", "REQ-001", 1): ScriptedTurn(
                {"artifacts/specifications/SPEC-001.md": spec_md}
            ),
            ("planner-agent", "SPEC-001", 1): ScriptedTurn(plan_files),
            ("worker-agent", "TASK-001", 1): ScriptedTurn(
                {fixture.test_path: fixture.test_source}
            ),
            ("worker-agent", "TASK-002", 1): ScriptedTurn({s_test: s_tsrc}),
            ("worker-agent", "TASK-003", 1): ScriptedTurn({fixture.impl_path: bad_src}),
            ("worker-agent", "TASK-003", 2): ScriptedTurn(
                {fixture.test_path: "// tampered\n"}
            ),
            ("worker-agent", "TASK-003", 3): ScriptedTurn(
                {fixture.impl_path: fixture.impl_source}
            ),
            ("worker-agent", "TASK-004", 1): ScriptedTurn({s_impl: s_isrc}),
            ("worker-agent", "TASK-004", 2): ScriptedTurn({s_impl: s_isrc}),
            ("worker-agent", "TASK-004", 3): ScriptedTurn({s_impl: s_isrc}),
        }
    )


@traces("REQ-055", "AC-04", "SPEC-055")
@pytest.mark.parametrize("fixture", ALL_LANGUAGE_FIXTURES, ids=ALL_LANGUAGE_IDS)
def test_multi_language_parallel_layers_and_merge_gate_faults_e2e(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Verify parallel multi-layer waves and MergeGate fault isolation."""
    _bootstrap_preset_pipeline_repo(tmp_path, fixture.preset)
    install_scripted_plan(monkeypatch, _build_parallel_wave_plan(fixture))
    capsys.readouterr()
    run_cmd = [
        "run",
        "--pipeline",
        "--max-workers",
        "2",
        "--agent-command",
        "mock",
        "--root",
        str(tmp_path),
    ]
    assert main(run_cmd) == 1
    out1 = capsys.readouterr().out
    assert "[CODE_PRINT_FORBIDDEN]" in out1 and "[ARCH_FORBIDDEN_IMPORT]" in out1
    assert not (tmp_path / fixture.impl_path).exists()
    by_id = load_artifacts_by_id(tmp_path)
    assert by_id["TASK-001"].frontmatter["status"] == "done"
    assert by_id["TASK-002"].frontmatter["status"] == "done"

    assert main(run_cmd) == 1
    out2 = capsys.readouterr().out
    assert "[PERM_LOCKED_TEST_CONTRACT]" in out2
    assert "[PERM_OUTSIDE_WRITE_SCOPE]" in out2

    assert main(run_cmd) == 0
    capsys.readouterr()
    assert main(["check", "all", "--root", str(tmp_path)]) == 0
    by_id_final = load_artifacts_by_id(tmp_path)
    assert by_id_final["TASK-003"].frontmatter["status"] == "done"
    assert by_id_final["TASK-004"].frontmatter["status"] == "done"


def _build_supersession_turns(
    fixture: LanguagePipelineFixture,
) -> dict[tuple[str, str, int], ScriptedTurn]:
    """Build INT-002 -> REQ-002 (supersedes REQ-001) -> SPEC-002 turns."""
    docs = _build_stage_artifacts(fixture)
    req2 = (
        docs["REQ"]
        .replace("id: REQ-001", "id: REQ-002")
        .replace("traces_to: [INT-001]", "traces_to: [INT-002]\nsupersedes: [REQ-001]")
        .replace("version: 1", "version: 2")
    )
    spec2 = docs["SPEC"].replace("SPEC-001", "SPEC-002").replace("REQ-001", "REQ-002")
    t3_md = (
        docs["TASK1"]
        .replace("id: TASK-001", "id: TASK-003")
        .replace("REQ-001, SPEC-001", "REQ-002, SPEC-002")
    )
    t4_md = (
        docs["TASK2"]
        .replace("id: TASK-002", "id: TASK-004")
        .replace("REQ-001, SPEC-001", "REQ-002, SPEC-002")
        .replace("depends_on: [TASK-001]", "depends_on: [TASK-003]")
    )
    test2_src = fixture.test_source.replace("REQ-001", "REQ-002").replace(
        "SPEC-001", "SPEC-002"
    )
    spec2_expect = (
        "### Artifact `REQ-001`",
        "### Artifact `SPEC-001`",
        f"### Target File `{fixture.impl_path}`",
        expected_fence(fixture.preset),
    )
    return {
        **build_base_turns(fixture),
        ("requirement-agent", "INT-002", 1): ScriptedTurn(
            {"artifacts/requirements/REQ-002.md": req2},
            ("### Existing Requirements Catalog", "- `REQ-001`:"),
        ),
        ("specification-agent", "REQ-002", 1): ScriptedTurn(
            {"artifacts/specifications/SPEC-002.md": spec2}, spec2_expect
        ),
        ("planner-agent", "SPEC-002", 1): ScriptedTurn(
            {"artifacts/tasks/TASK-003.md": t3_md, "artifacts/tasks/TASK-004.md": t4_md}
        ),
        ("worker-agent", "TASK-003", 1): ScriptedTurn({fixture.test_path: test2_src}),
        ("worker-agent", "TASK-004", 1): ScriptedTurn(
            {fixture.impl_path: fixture.impl_source}
        ),
    }


@traces("REQ-055", "AC-04", "SPEC-055")
@pytest.mark.parametrize("fixture", ALL_LANGUAGE_FIXTURES, ids=ALL_LANGUAGE_IDS)
def test_multi_language_requirement_supersession_e2e(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Verify INT-002 Requirement supersession and target file context."""
    _bootstrap_preset_pipeline_repo(tmp_path, fixture.preset)
    install_scripted_plan(
        monkeypatch, ScriptedPlan(turns=_build_supersession_turns(fixture))
    )
    run_cmd = ["run", "--pipeline", "--agent-command", "mock", "--root", str(tmp_path)]
    assert main(run_cmd) == 0
    assert main(["intent", "Evolve calculation.", "--root", str(tmp_path)]) == 0
    commit_traceable_change(
        tmp_path,
        ["artifacts/intents/INT-002.md"],
        "INT-002: Add evolution intent [traces: INT-002]",
    )
    capsys.readouterr()
    assert main(run_cmd) == 0
    capsys.readouterr()
    assert main(["check", "all", "--root", str(tmp_path)]) == 0
    by_id = load_artifacts_by_id(tmp_path)
    assert by_id["REQ-001"].frontmatter["status"] == "deprecated"
    assert by_id["SPEC-001"].frontmatter["status"] == "deprecated"
    assert by_id["REQ-002"].frontmatter["status"] == "approved"
    assert by_id["SPEC-002"].frontmatter["status"] == "approved"
    assert by_id["INT-002"].frontmatter["status"] == "processed"
    assert any(fixture.test_path in line for line in trace_lineage(tmp_path, "REQ-002"))
