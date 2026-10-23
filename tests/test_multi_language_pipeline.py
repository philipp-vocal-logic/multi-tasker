"""TestContracts for multi-language checkers, presets, prompts, and E2E pipelines."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import yaml

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.checkers.clean_code_checker import check_clean_code
from multi_tasker.checkers.glossary_checker import check_glossary
from multi_tasker.checkers.limits_checker import check_limits
from multi_tasker.checkers.traceability_checker import check_traceability
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_artifacts_by_id, load_yaml_file
from multi_tasker.orchestrator.interaction_logger import record_task_event
from multi_tasker.orchestrator.lineage import trace_lineage
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from multi_tasker.orchestrator.worktree import commit_traceable_change


def _write_file(path: Path, content: str) -> None:
    """Create parent directories and write UTF-8 text to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_architecture_and_glossary_policies(tmp_path: Path) -> None:
    """Seed glossary.yaml and code_architecture.yaml for multi-language checks."""
    glossary = {
        "enforcement": {"check_code_identifiers": True},
        "terms": [
            {
                "canonical": "Task",
                "allowed_forms": ["Task", "task"],
                "code_identifiers": ["Task", "task", "task_id"],
                "forbidden_synonyms": ["WorkItem"],
            }
        ],
    }
    architecture = {
        "dependency_rules": {"forbid_circular_imports": True},
        "allowed_third_party_packages": [],
        "layers": [
            {
                "name": "domain",
                "paths": ["src/domain/**"],
                "allowed_internal_imports": ["src.domain", "domain"],
                "forbidden_internal_imports": ["src.cli", "cli", "tests"],
            }
        ],
    }
    _write_file(tmp_path / "policy/glossary.yaml", yaml.safe_dump(glossary))
    _write_file(
        tmp_path / "policy/code_architecture.yaml", yaml.safe_dump(architecture)
    )


def _seed_multi_language_checker_fixture(tmp_path: Path) -> None:
    """Seed policies and violating ANSI C and Rust files for checker validation."""
    marker = "TO" + "DO"
    quality = {
        "language": "ansi-c",
        "source_extensions": [".c", ".h", ".rs"],
        "linters": {"ruff": {"enabled": False}, "mypy": {"enabled": False}},
        "ast_rules": {
            "forbid_todo_fixme_comments": True,
            "forbidden_comment_markers": [marker],
            "forbid_pass_only_functions_in_src": True,
            "forbidden_calls_in_src": ["printf", "println"],
            "min_identifier_length": 3,
            "allowed_single_char_names": ["_"],
        },
    }
    limits = {
        "source_code": {
            "max_file_lines": 40,
            "refactor_target_file_lines": 35,
            "max_function_lines": 5,
            "max_function_args": 2,
            "max_docstring_lines": 2,
            "max_docstring_words": 10,
            "max_inline_comment_lines": 2,
            "max_inline_comment_words": 10,
        }
    }
    _write_file(tmp_path / "policy/code_quality.yaml", yaml.safe_dump(quality))
    _write_file(tmp_path / "policy/code_limits.yaml", yaml.safe_dump(limits))
    _seed_architecture_and_glossary_policies(tmp_path)


def _write_violating_c_and_rust_sources(tmp_path: Path) -> None:
    """Write C and Rust files triggering clean_code, limits, glossary, and arch."""
    marker = "TO" + "DO"
    c_source = (
        "/**\n * Line one.\n * Line two.\n * Line three.\n */\n"
        '#include "cli/header.h"\n#include "domain/other.h"\n#include <ext_lib.h>\n'
        f"/* {marker}: fix later */\nint empty_stub(int q) {{}}\n"
        "int compute_work_item(int alpha, int beta, int gamma) {\n"
        "    /* c1 */\n    /* c2 */\n    /* c3 */\n"
        '    int x = alpha + beta;\n    printf("%d", x);\n    return x + gamma;\n}\n'
    )
    _write_file(tmp_path / "src/domain/calc.c", c_source)
    _write_file(tmp_path / "src/domain/other.h", '#include "domain/calc.c"\n')
    rust_source = (
        "//! Doc line one.\n//! Doc line two.\n//! Doc line three.\n"
        "use crate::cli::runner;\n"
        "pub fn rust_stub(z: i32) -> i32 { todo!() }\n"
        "pub fn tAsK(first: i32, second: i32, third: i32) -> i32 {\n"
        '    println!("{}", first);\n    first + second + third\n}\n'
    )
    _write_file(tmp_path / "src/domain/calc.rs", rust_source)


@traces("REQ-052", "AC-01", "SPEC-052")
def test_ansi_c_and_rust_checkers_enforce_limits_clean_code_glossary_and_architecture(
    tmp_path: Path,
) -> None:
    """Verify clean_code, limits, glossary, architecture, and traceability on C/Rust."""
    _seed_multi_language_checker_fixture(tmp_path)
    _write_violating_c_and_rust_sources(tmp_path)
    clean_rules = {finding.rule_id for finding in check_clean_code(tmp_path)}
    assert {"CODE_FORBIDDEN_MARKER", "CODE_STUB_FUNCTION"} <= clean_rules
    assert {"CODE_SHORT_IDENT", "CODE_PRINT_FORBIDDEN"} <= clean_rules
    limit_rules = {finding.rule_id for finding in check_limits(tmp_path)}
    assert {"LIMIT_DOCSTRING_LINES", "LIMIT_FUNC_LINES"} <= limit_rules
    assert {"LIMIT_FUNC_ARGS", "LIMIT_COMMENT_LEN"} <= limit_rules
    glossary_rules = {finding.rule_id for finding in check_glossary(tmp_path)}
    assert {"GLOSSARY_FORBIDDEN_IDENT", "GLOSSARY_CASE_MISMATCH"} <= glossary_rules
    arch_rules = {finding.rule_id for finding in check_architecture(tmp_path)}
    assert {"ARCH_FORBIDDEN_IMPORT", "ARCH_THIRD_PARTY_FORBIDDEN"} <= arch_rules
    assert "ARCH_CIRCULAR_IMPORT" in arch_rules


@traces("REQ-052", "AC-01", "SPEC-052")
@traces("REQ-052", "AC-02", "SPEC-052")
def test_initialize_presets_and_prompt_synthesis_for_ansi_c_and_rust(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify ansi-c and rust presets, prompt code contracts, and non-Python traces."""
    c_root, rust_root = tmp_path / "c_repo", tmp_path / "rust_repo"
    assert main(["initialize", "--preset", "ansi-c", "--root", str(c_root)]) == 0
    assert main(["initialize", "--preset", "rust", "--root", str(rust_root)]) == 0
    capsys.readouterr()
    c_quality = load_yaml_file(c_root / "policy/code_quality.yaml")
    rust_quality = load_yaml_file(rust_root / "policy/code_quality.yaml")
    assert c_quality["language"] == "ansi-c"
    assert rust_quality["language"] == "rust"
    c_prompt, c_errors = build_agent_prompt(c_root, "worker-agent")
    rust_prompt, rust_errors = build_agent_prompt(rust_root, "worker-agent")
    assert not c_errors and not rust_errors
    assert "```c" in c_prompt and '@traces("REQ-NNN"' in c_prompt
    assert "```rust" in rust_prompt and "#[test]" in rust_prompt
    _write_file(c_root / "tests/test_sample.c", "void test_untagged_case(void) {}\n")
    trace_rules = {finding.rule_id for finding in check_traceability(c_root)}
    assert "TRACE_UNTAGGED_TEST" in trace_rules


@dataclass(frozen=True)
class LanguagePipelineFixture:
    """Language-specific artifact paths, commands, and source files for E2E runs."""

    preset: str
    test_path: str
    impl_path: str
    test_cmd: str
    impl_cmd: str
    test_source: str
    impl_source: str


_PY_FIXTURE = LanguagePipelineFixture(
    "python",
    "tests/test_calc.py",
    "src/domain/calc.py",
    "python3 -m py_compile tests/test_calc.py",
    "pytest -q tests/test_calc.py",
    (
        '"""TestContract for Python calculation."""\n\n'
        "from multi_tasker.domain.models import traces\n"
        "from src.domain.calc import add_values\n\n\n"
        '@traces("REQ-001", "AC-01", "SPEC-001")\n'
        "def test_add_values() -> None:\n"
        '    """Verify add_values returns sum."""\n'
        "    assert add_values(2, 3) == 5\n"
    ),
    (
        '"""Python calculation implementation."""\n\n\n'
        "def add_values(left: int, right: int) -> int:\n"
        '    """Return sum of left and right integers."""\n'
        "    return left + right\n"
    ),
)

_C_FIXTURE = LanguagePipelineFixture(
    "ansi-c",
    "tests/test_calc.c",
    "src/domain/calc.c",
    "gcc -std=c89 -pedantic -Wall -Wextra -Werror -fsyntax-only tests/test_calc.c",
    (
        'sh -c "gcc -std=c89 -pedantic -Wall -Wextra -Werror '
        'tests/test_calc.c src/domain/calc.c -o .report/test_calc && .report/test_calc"'
    ),
    (
        "/** TestContract for ANSI C calculation. */\n#include <assert.h>\n\n"
        "int add_values(int left, int right);\n\n"
        '/* @traces("REQ-001", "AC-01", "SPEC-001") */\n'
        "void test_add_values(void) {\n    assert(add_values(2, 3) == 5);\n}\n\n"
        "int main(void) {\n    test_add_values();\n    return 0;\n}\n"
    ),
    (
        "/** ANSI C calculation implementation. */\n\n"
        "int add_values(int left, int right) {\n    return left + right;\n}\n"
    ),
)

_RUST_FIXTURE = LanguagePipelineFixture(
    "rust",
    "tests/test_calc.rs",
    "src/domain/calc.rs",
    "rustfmt --check --edition 2021 --config skip_children=true tests/test_calc.rs",
    (
        'sh -c "rustc --edition 2021 --test tests/test_calc.rs '
        '-o .report/test_calc && .report/test_calc --quiet"'
    ),
    (
        "//! TestContract for Rust calculation.\n\n"
        '#[path = "../src/domain/calc.rs"]\nmod calc;\n\n'
        '// @traces("REQ-001", "AC-01", "SPEC-001")\n#[test]\n'
        "fn test_add_values() {\n    assert_eq!(calc::add_values(2, 3), 5);\n}\n"
    ),
    (
        "//! Rust calculation implementation.\n\n"
        "pub fn add_values(left: i32, right: i32) -> i32 {\n    left + right\n}\n"
    ),
)


def _build_stage_artifacts(fixture: LanguagePipelineFixture) -> dict[str, str]:
    """Build REQ-001, SPEC-001, TASK-001, and TASK-002 Markdown texts for fixture."""
    req_md = (
        "---\nid: REQ-001\ntitle: Calculation Service Requirement\n"
        "status: in_review\ntraces_to: [INT-001]\ndecisions: []\n"
        "acceptance_criteria:\n  - id: AC-01\n    given: Two integers\n"
        "    when: Added together\n    then: Returns exact sum\n"
        "version: 1\n---\n## Statement\nProvide integer addition.\n\n"
        f"## Impact Analysis\nAdds {fixture.impl_path} and {fixture.test_path}.\n"
    )
    spec_md = (
        "---\nid: SPEC-001\ntitle: Calculation Service Specification\n"
        "status: in_review\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01]\ndecisions: []\n"
        f"target_files:\n  tests: [{fixture.test_path}]\n"
        f"  implementation: [{fixture.impl_path}]\n---\n"
        f"## Design Overview\nImplement add_values in {fixture.impl_path}.\n\n"
        "## Public Interfaces\nadd_values(left, right)\n\n"
        f"## Test Contract Mapping\n- REQ-001:AC-01 -> {fixture.test_path}\n"
    )
    task1_md = (
        "---\nid: TASK-001\ntitle: Author Calculation TestContract\n"
        "type: test_contract\nstatus: ready\ntraces_to: [REQ-001, SPEC-001]\n"
        f"depends_on: []\nrequired_files: []\nwrite_files: [{fixture.test_path}]\n"
        f"verification_cmd: '{fixture.test_cmd}'\n---\n"
        f"## Objective\nWrite {fixture.test_path}.\n\n"
        f"## Scoped Instructions\nCreate {fixture.test_path}.\n"
    )
    task2_md = (
        "---\nid: TASK-002\ntitle: Implement Calculation Module\n"
        "type: implementation\nstatus: ready\ntraces_to: [REQ-001, SPEC-001]\n"
        f"depends_on: [TASK-001]\nrequired_files: [{fixture.test_path}]\n"
        f"write_files: [{fixture.impl_path}]\n"
        f"verification_cmd: '{fixture.impl_cmd}'\n---\n"
        f"## Objective\nWrite {fixture.impl_path}.\n\n"
        f"## Scoped Instructions\nCreate {fixture.impl_path}.\n"
    )
    return {"REQ": req_md, "SPEC": spec_md, "TASK1": task1_md, "TASK2": task2_md}


def _install_language_pipeline_mock(
    monkeypatch: pytest.MonkeyPatch, fixture: LanguagePipelineFixture
) -> None:
    """Install mocked stage and worker hooks for a language pipeline fixture."""
    from multi_tasker.orchestrator import stage_runner, task_runner

    docs = _build_stage_artifacts(fixture)
    stage_outputs = {
        ("requirement-agent", "INT-001"): {
            "artifacts/requirements/REQ-001.md": docs["REQ"]
        },
        ("specification-agent", "REQ-001"): {
            "artifacts/specifications/SPEC-001.md": docs["SPEC"]
        },
        ("planner-agent", "SPEC-001"): {
            "artifacts/tasks/TASK-001.md": docs["TASK1"],
            "artifacts/tasks/TASK-002.md": docs["TASK2"],
        },
    }
    worker_outputs = {
        "TASK-001": {fixture.test_path: fixture.test_source},
        "TASK-002": {fixture.impl_path: fixture.impl_source},
    }

    def _stage_hook(
        worktree_path: Path, role: str, doc: Any, ctx: tuple[str, str, str]
    ) -> list[str]:
        before = stage_runner._snapshot_artifacts(worktree_path)
        target_id = str(doc.frontmatter["id"])
        for rel_path, text in stage_outputs[(role, target_id)].items():
            _write_file(worktree_path / rel_path, text)
        details = {"command": "mock", "return_code": 0, "duration_ms": 1}
        record_task_event(
            worktree_path, target_id, "agent_invocation", details, ctx, role
        )
        return stage_runner._detect_stage_changes(worktree_path, before, target_id)

    def _worker_hook(
        worktree_path: Path, doc: Any, ctx: tuple[str, str, str], timeout: float = 300.0
    ) -> list[str]:
        _ = timeout
        task_id = str(doc.frontmatter["id"])
        for rel_path, text in worker_outputs[task_id].items():
            _write_file(worktree_path / rel_path, text)
        details = {"command": "mock", "return_code": 0, "duration_ms": 1}
        record_task_event(worktree_path, task_id, "agent_invocation", details, ctx)
        return list(worker_outputs[task_id].keys())

    monkeypatch.setattr(stage_runner, "_run_stage_subprocess", _stage_hook)
    monkeypatch.setattr(task_runner, "_invoke_agent_in_worktree", _worker_hook)


def _bootstrap_preset_pipeline_repo(repository_root: Path, preset: str) -> None:
    """Initialize repository with preset, enable auto gates, and commit INT-001."""
    assert main(["initialize", "--preset", preset, "--root", str(repository_root)]) == 0
    pipeline_path = repository_root / "policy/artifact_lifecycle.yaml"
    pipeline = load_yaml_file(pipeline_path)
    for stage in pipeline.get("stages", []):
        stage["approval_gate"] = "auto"
    pipeline_path.write_text(yaml.safe_dump(pipeline), encoding="utf-8")
    quality_path = repository_root / "policy/code_quality.yaml"
    quality = load_yaml_file(quality_path)
    for linter_cfg in quality.get("linters", {}).values():
        if isinstance(linter_cfg, dict):
            linter_cfg["enabled"] = False
    quality_path.write_text(yaml.safe_dump(quality), encoding="utf-8")
    assert (
        main(["intent", "Build calculation module.", "--root", str(repository_root)])
        == 0
    )
    tracked = [
        ".gitignore",
        "AGENTS.md",
        "artifacts/intents/INT-001.md",
        *(f"policy/{yml.name}" for yml in (repository_root / "policy").glob("*.yaml")),
    ]
    commit_traceable_change(
        repository_root, tracked, "INT-001: Bootstrap preset [traces: INT-001]"
    )


@traces("REQ-052", "AC-03", "SPEC-052")
@pytest.mark.parametrize(
    "fixture",
    (_PY_FIXTURE, _C_FIXTURE, _RUST_FIXTURE),
    ids=("python", "ansi-c", "rust"),
)
def test_end_to_end_pipeline_execution_across_python_ansi_c_and_rust(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    fixture: LanguagePipelineFixture,
) -> None:
    """Execute full INT->REQ->SPEC->TASK pipeline for Python, ANSI C, and Rust."""
    _bootstrap_preset_pipeline_repo(tmp_path, fixture.preset)
    _install_language_pipeline_mock(monkeypatch, fixture)
    capsys.readouterr()
    run_cmd = ["run", "--pipeline", "--agent-command", "mock", "--root", str(tmp_path)]
    assert main(run_cmd) == 0
    done = tuple(dict.fromkeys(capsys.readouterr().out.strip().splitlines()))
    assert done == ("REQ-001", "SPEC-001", "TASK-001", "TASK-002")
    assert main(["check", "all", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == ""
    by_id = load_artifacts_by_id(tmp_path)
    assert by_id["INT-001"].frontmatter["status"] == "processed"
    assert by_id["TASK-001"].frontmatter["status"] == "done"
    assert by_id["TASK-002"].frontmatter["status"] == "done"
    assert any(fixture.test_path in line for line in trace_lineage(tmp_path, "REQ-001"))
