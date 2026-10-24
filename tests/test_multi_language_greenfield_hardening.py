"""TestContracts for greenfield multi-language checker, preset, and prompt hardening."""

from pathlib import Path

import pytest

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.checkers.clean_code_checker import check_clean_code
from multi_tasker.checkers.limits_checker import check_limits
from multi_tasker.checkers.language_support import extract_non_python_test_functions
from multi_tasker.checkers.traceability_checker import check_traceability
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from multi_tasker.orchestrator.worktree import commit_traceable_change, create_worktree


def _write_text(path: Path, content: str) -> None:
    """Create parent directories and write UTF-8 text to path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _verify_preset_layer_boundaries(base_dir: Path) -> None:
    """Verify domain, services, and cli layer boundaries across all 3 presets."""
    cases = [
        (
            "python",
            "src/domain/model.py",
            "import src.services.helper\n",
            "src/services/helper.py",
            "import src.cli.app\n",
            "src/cli/app.py",
            "import src.services.helper\nimport src.domain.model\n",
        ),
        (
            "ansi-c",
            "src/domain/model.c",
            '#include "services/helper.h"\n',
            "src/services/helper.c",
            '#include "cli/app.h"\n',
            "src/cli/app.c",
            '#include "services/helper.h"\n#include "domain/model.h"\n',
        ),
        (
            "rust",
            "src/domain/model.rs",
            "use crate::services::helper;\n",
            "src/services/helper.rs",
            "use crate::cli::app;\n",
            "src/cli/app.rs",
            "use crate::services::helper;\nuse crate::domain::model;\n",
        ),
    ]
    for preset, dom_file, dom_bad, svc_file, svc_bad, cli_file, cli_ok in cases:
        repo = base_dir / f"layers_{preset}"
        assert main(["initialize", "--preset", preset, "--root", str(repo)]) == 0
        _write_text(repo / dom_file, dom_bad)
        _write_text(repo / svc_file, svc_bad)
        _write_text(repo / cli_file, cli_ok)
        findings = check_architecture(repo)
        by_path = {item.path: item.rule_id for item in findings}
        assert by_path.get(dom_file) == "ARCH_FORBIDDEN_IMPORT"
        assert by_path.get(svc_file) == "ARCH_FORBIDDEN_IMPORT"
        assert cli_file not in by_path


def _verify_c_includes_and_greenfield_mypy(base_dir: Path) -> None:
    """Verify C self/relative header includes and Python greenfield mypy checks."""
    c_repo = base_dir / "c_includes"
    assert main(["initialize", "--preset", "ansi-c", "--root", str(c_repo)]) == 0
    _write_text(c_repo / "src/domain/calc.h", "int add_values(int left, int right);\n")
    _write_text(
        c_repo / "src/domain/calc.c",
        '#include "calc.h"\n#include "domain/calc.h"\n#include <inttypes.h>\n'
        "int add_values(int left, int right) { return left + right; }\n",
    )
    _write_text(c_repo / "src/top.h", "int top_value(void);\n")
    _write_text(
        c_repo / "src/top.c",
        '#include "top.h"\nint top_value(void) { return 1; }\n',
    )
    assert check_architecture(c_repo) == []

    py_repo = base_dir / "py_mypy"
    assert main(["initialize", "--preset", "python", "--root", str(py_repo)]) == 0
    test_code = (
        '"""TestContract for clamp."""\n\n'
        "from multi_tasker.domain.models import traces\n"
        "from src.domain.bounds import clamp_value\n\n\n"
        '@traces("REQ-001", "AC-01", "SPEC-001")\n'
        "def test_clamp_value() -> None:\n"
        '    """Verify clamp_value."""\n'
        "    assert clamp_value(5) == 5\n"
    )
    _write_text(py_repo / "tests/test_bounds.py", test_code)
    assert check_clean_code(py_repo, ["tests/test_bounds.py"]) == []
    _write_text(
        py_repo / "src/domain/bounds.py",
        '"""Bounds module."""\n\n\n'
        "def clamp_value(value: int) -> int:\n"
        '    """Return clamped value."""\n'
        "    return value\n",
    )
    assert check_clean_code(py_repo) == []


@traces("REQ-053", "AC-01", "SPEC-053")
def test_layer_globs_c_self_and_relative_includes_and_greenfield_mypy(
    tmp_path: Path,
) -> None:
    """Verify preset layer globs, C self/relative includes, and greenfield mypy."""
    _verify_preset_layer_boundaries(tmp_path)
    _verify_c_includes_and_greenfield_mypy(tmp_path)


def _verify_c_and_rust_comment_and_string_sanitization(base_dir: Path) -> None:
    """Verify comments, strings, generics, where clauses, and super imports pass."""
    c_repo = base_dir / "c_sanitize"
    assert main(["initialize", "--preset", "ansi-c", "--root", str(c_repo)]) == 0
    c_marker = "TO" + "DO"
    _write_text(
        c_repo / "src/domain/clean.c",
        "/** Clean C module where int a and printf(x) appear in comment. */\n"
        "int format_label(int count, int limit) {\n"
        "    /* let a = 1; char b = 2; printf(x); */\n"
        f'    const char *url = "https://example.com//{c_marker}}}";\n'
        "    unsigned int total = count + limit + (int)url[0];\n"
        "    return (int)total;\n"
        "}\n",
    )
    assert check_clean_code(c_repo) == []
    assert check_limits(c_repo) == []

    rust_repo = base_dir / "rust_sanitize"
    assert main(["initialize", "--preset", "rust", "--root", str(rust_repo)]) == 0
    _write_text(
        rust_repo / "src/domain/clean.rs",
        "//! Clean Rust module where let a and println!(x) appear in docs.\n"
        "use std::collections::HashMap;\n"
        "use super::helper;\n"
        "use crate::domain::{first_mod, second_mod};\n"
        'pub fn emit_brace() -> &\'static str { "}" }\n'
        "pub fn pair_values<T>(items: HashMap<String, i32>, val: T) -> [i32; 2]\n"
        "where\n"
        "    T: Clone,\n"
        "{\n"
        '    let brace_literal = "} // not a comment";\n'
        "    let count = items.len() as i32 + brace_literal.len() as i32;\n"
        "    let _cloned = val.clone();\n"
        "    [count, count]\n"
        "}\n",
    )
    assert check_clean_code(rust_repo) == []
    assert check_limits(rust_repo) == []
    assert check_architecture(rust_repo) == []


@traces("REQ-053", "AC-02", "SPEC-053")
@traces("REQ-054", "AC-01", "SPEC-054")
@traces("REQ-054", "AC-02", "SPEC-054")
def test_c_and_rust_comment_string_sanitization_and_signature_trace_parsing(
    tmp_path: Path,
) -> None:
    """Verify C/Rust sanitization, multi-word C variables, and @traces isolation."""
    _verify_c_and_rust_comment_and_string_sanitization(tmp_path)
    c_repo = tmp_path / "c_vars"
    assert main(["initialize", "--preset", "ansi-c", "--root", str(c_repo)]) == 0
    _write_text(
        c_repo / "src/domain/short_vars.c",
        "/** Short variable check. */\n"
        "#include <stdbool.h>\n#include <stdint.h>\n"
        "int compute_values(int alpha) {\n"
        "    unsigned int x = 1;\n"
        "    const int w = 2;\n"
        "    int32_t a = 3;\n"
        "    bool c = true;\n"
        "    return alpha + (int)x + w + (int)a + (int)c;\n"
        "}\n",
    )
    short_findings = [
        item for item in check_clean_code(c_repo) if item.rule_id == "CODE_SHORT_IDENT"
    ]
    assert len(short_findings) == 4

    _write_text(
        c_repo / "tests/test_traces.c",
        '/* @traces("REQ-001", "AC-01", "SPEC-001") */\n'
        '/* @traces("REQ-001", "AC-02", "SPEC-001") */\n'
        '/* @traces("REQ-001", "AC-03", "SPEC-001") */\n'
        '/* @traces("REQ-001", "AC-04", "SPEC-001") */\n'
        '/* @traces("REQ-001", "AC-05", "SPEC-001") */\n'
        "void test_five_criteria(void) {}\n"
        "void test_untagged_after_short_fn(void) {}\n",
    )
    trace_findings = check_traceability(c_repo)
    untagged = [
        item.message for item in trace_findings if item.rule_id == "TRACE_UNTAGGED_TEST"
    ]
    assert any("test_untagged_after_short_fn" in msg for msg in untagged)
    assert not any("test_five_criteria" in msg for msg in untagged)
    extracted = extract_non_python_test_functions(
        (c_repo / "tests/test_traces.c").read_text(encoding="utf-8")
    )
    assert len(extracted[0][2]) == 5 and extracted[1][2] == []


def _seed_task_for_prompt_check(repo: Path) -> None:
    """Seed minimal REQ-001, SPEC-001, and TASK-001 in repo for prompt testing."""
    _write_text(
        repo / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\ntitle: Sample Requirement\nstatus: approved\n"
        "traces_to: [INT-001]\ndecisions: []\nacceptance_criteria:\n"
        "  - id: AC-01\n    given: Input\n    when: Run\n    then: Output\n"
        "version: 1\n---\n## Statement\nSample.\n\n## Impact Analysis\nSample.\n",
    )
    _write_text(
        repo / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\ntitle: Sample Specification\nstatus: approved\n"
        "traces_to: [REQ-001]\ncovers_criteria: [REQ-001:AC-01]\ndecisions: []\n"
        "target_files:\n  tests: [tests/test_sample.c]\n"
        "  implementation: [src/domain/sample.c]\n---\n"
        "## Design Overview\nSample.\n\n## Public Interfaces\nSample.\n\n"
        "## Test Contract Mapping\n- REQ-001:AC-01 -> tests/test_sample.c\n",
    )
    _write_text(
        repo / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\ntitle: Sample TestContract Task\ntype: test_contract\n"
        "status: in_review\ntraces_to: [REQ-001, SPEC-001]\ndepends_on: []\n"
        "required_files: []\nwrite_files: [tests/test_sample.c]\n"
        "verification_cmd: gcc -fsyntax-only tests/test_sample.c\n---\n"
        "## Objective\nWrite test.\n\n## Scoped Instructions\nWrite test.\n",
    )


@traces("REQ-053", "AC-03", "SPEC-053")
def test_review_prompt_scope_worktree_report_dir_and_non_python_documentation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify review-agent prompt paths, worktree .report dir, and C documentation."""
    c_repo = tmp_path / "c_orch"
    assert main(["initialize", "--preset", "ansi-c", "--root", str(c_repo)]) == 0
    assert main(["intent", "Build sample.", "--root", str(c_repo)]) == 0
    _seed_task_for_prompt_check(c_repo)
    capsys.readouterr()

    review_prompt, rev_err = build_agent_prompt(c_repo, "review-agent", "TASK-001")
    worker_prompt, wrk_err = build_agent_prompt(c_repo, "worker-agent", "TASK-001")
    assert not rev_err and not wrk_err
    assert "--paths artifacts/reviews/REV-" in review_prompt
    assert "--paths tests/test_sample.c" not in review_prompt
    assert "--paths tests/test_sample.c" in worker_prompt
    assert "from multi_tasker.domain.models import traces" not in review_prompt

    trace_policy = load_yaml_file(c_repo / "policy/traceability.yaml")
    impl_cmd = trace_policy["traceability_rules"]["implementation_verification_cmd"]
    assert "mkdir -p .report" in impl_cmd and "find src" in impl_cmd

    tracked = [
        ".gitignore",
        "AGENTS.md",
        "artifacts/intents/INT-001.md",
        "artifacts/requirements/REQ-001.md",
        "artifacts/specifications/SPEC-001.md",
        "artifacts/tasks/TASK-001.md",
        *(f"policy/{yml.name}" for yml in (c_repo / "policy").glob("*.yaml")),
    ]
    commit_traceable_change(c_repo, tracked, "TASK-001: Seed [traces: INT-001]")
    worktree_dir = create_worktree(c_repo, "test-wt")
    assert (worktree_dir / ".report").is_dir()

    _write_text(c_repo / "src/domain/sample.c", "int sample(void) { return 1; }\n")
    _write_text(
        c_repo / "tests/test_sample.c",
        '/* @traces("REQ-001", "AC-01", "SPEC-001") */\nvoid test_sample(void) {}\n',
    )
    assert main(["documentation", "--root", str(c_repo)]) == 0
    spec_report = (c_repo / ".report/specification.md").read_text(encoding="utf-8")
    assert "Pytest Exit Code" not in spec_report
