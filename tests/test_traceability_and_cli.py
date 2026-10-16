"""Parametrized TestContracts for clean_code, architecture, traceability, and CLI."""

from pathlib import Path
import subprocess
from typing import Any

import pytest
import yaml

from src.checkers.architecture_checker import check_architecture
from src.checkers.clean_code_checker import check_clean_code
from src.checkers.runner import run_single_check
from src.checkers.schemas_checker import check_schemas, validate_schema_node
from src.checkers.traceability_checker import check_traceability
from src.cli.main import main
from src.domain.models import traces
from src.orchestrator.worktree import commit_traceable_change

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _write_document(path: Path, content: str) -> None:
    """Create parent directories and write file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@traces("REQ-001", "AC-03", "SPEC-001")
def test_clean_code_checker_violation_branches(tmp_path: Path) -> None:
    """Verify AST code rules (markers, return types, stubs, short names, print)."""
    assert check_clean_code(tmp_path)[0].rule_id == "CODE_POLICY_MISSING"
    marker = "FIX" + "ME"
    _write_document(
        tmp_path / "policy" / "clean_code.yaml",
        yaml.safe_dump(
            {
                "linters": {"ruff": {"enabled": True, "select_rules": ["F"]}},
                "ast_rules": {
                    "forbidden_comment_markers": [marker],
                    "allowed_single_char_names": ["_"],
                },
            }
        ),
    )
    _write_document(
        tmp_path / "src" / "domain" / "a.py",
        f"import os\n# {marker}\ndef stub(q: int):\n    ...\n"
        "def run() -> None:\n    z = 1\n    try:\n        print(z)\n"
        "    except:\n        return None\n",
    )
    code_rules = {finding.rule_id for finding in check_clean_code(tmp_path)}
    assert {
        "CODE_F401",
        "CODE_FORBIDDEN_MARKER",
        "CODE_MISSING_RETURN_TYPE",
        "CODE_STUB_FUNCTION",
        "CODE_SHORT_IDENT",
        "CODE_BARE_EXCEPT",
        "CODE_PRINT_FORBIDDEN",
    }.issubset(code_rules)


@traces("REQ-001", "AC-03", "SPEC-001")
def test_architecture_checker_violation_branches(tmp_path: Path) -> None:
    """Verify architecture circular, third-party, and layer rules."""
    assert check_architecture(tmp_path)[0].rule_id == "ARCH_POLICY_MISSING"
    layer_configuration = {
        "name": "dom",
        "paths": ["src/domain/**"],
        "allowed_internal_imports": ["src.domain"],
    }
    _write_document(
        tmp_path / "policy" / "architecture.yaml",
        yaml.safe_dump(
            {
                "dependency_rules": {"forbid_circular_imports": True},
                "allowed_third_party_packages": [],
                "layers": [layer_configuration],
            }
        ),
    )
    _write_document(
        tmp_path / "src" / "domain" / "a.py",
        "import ext_pkg\nfrom . import b\nfrom ..cli import main\n",
    )
    _write_document(tmp_path / "src" / "domain" / "b.py", "from .a import run\n")
    _write_document(tmp_path / "src" / "other.py", "val = 1\n")
    architecture_rules = {finding.rule_id for finding in check_architecture(tmp_path)}
    assert {
        "ARCH_THIRD_PARTY_FORBIDDEN",
        "ARCH_FORBIDDEN_IMPORT",
        "ARCH_CIRCULAR_IMPORT",
        "ARCH_UNKNOWN_LAYER",
    }.issubset(architecture_rules)
    scoped = {
        finding.rule_id for finding in check_architecture(tmp_path, ["src/other.py"])
    }
    assert "ARCH_UNKNOWN_LAYER" in scoped


@traces("REQ-001", "AC-04", "SPEC-001")
@pytest.mark.parametrize(
    ("value", "schema", "expected_rule"),
    [
        ("not-int", {"type": "integer"}, "TRACE_SCHEMA_TYPE"),
        (True, {"type": "integer"}, "TRACE_SCHEMA_TYPE"),
        (123, {"type": ["string", "null"]}, "TRACE_SCHEMA_TYPE"),
        ("bad", {"type": "string", "enum": ["ok"]}, "TRACE_SCHEMA_ENUM"),
        (0, {"type": "integer", "minimum": 1}, "TRACE_SCHEMA_MIN"),
        ("abc", {"type": "string", "pattern": "^REQ-"}, "TRACE_SCHEMA_PATTERN"),
        ("ab", {"type": "string", "minLength": 5}, "TRACE_SCHEMA_MIN_LEN"),
        ("abcdef", {"type": "string", "maxLength": 3}, "TRACE_SCHEMA_MAX_LEN"),
        ([], {"type": "array", "minItems": 1}, "TRACE_SCHEMA_MIN_ITEMS"),
        ([1, 2], {"type": "array", "maxItems": 1}, "TRACE_SCHEMA_MAX_ITEMS"),
        ({}, {"type": "object", "required": ["id"]}, "TRACE_SCHEMA_REQUIRED"),
        (
            {"id": "1", "extra": 2},
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"id": {"type": "string"}},
            },
            "TRACE_SCHEMA_UNKNOWN_FIELD",
        ),
    ],
)
def test_schemas_checker_branches(
    value: Any, schema: dict[str, Any], expected_rule: str
) -> None:
    """Verify every JSON-Schema validation rule in memory."""
    findings = validate_schema_node(value, schema, "artifact.md", "field")
    assert expected_rule in {finding.rule_id for finding in findings}
    assert validate_schema_node(None, {"type": ["string", "null"]}, "a.md") == []
    assert validate_schema_node(True, {"type": "boolean"}, "a.md") == []


def _seed_trace_fixtures(tmp_path: Path) -> None:
    """Create synthetic artifacts and test files for trace failure testing."""
    _write_document(
        tmp_path / "policy/schemas.yaml",
        "schemas: {REQ: {path_glob: 'artifacts/requirements/REQ-*.md'}}\n",
    )
    _write_document(tmp_path / "policy/traceability.yaml", "traceability_rules: {}\n")
    documents = {
        "artifacts/wrong_folder/REQ-099.md": "---\nid: REQ-099\nstatus: draft\n---\n",
        "artifacts/requirements/REQ-001.md": (
            "---\nid: REQ-001\nstatus: draft\ntraces_to: [INT-404]\n---\n"
        ),
        "artifacts/requirements/REQ-002.md": (
            "---\nid: REQ-002\nstatus: approved\n"
            "acceptance_criteria: [{id: AC-01}, {id: AC-02}]\n---\n"
        ),
        "artifacts/specifications/SPEC-001.md": (
            "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n"
            "covers_criteria: [REQ-002:AC-01]\n"
            "target_files: {tests: [tests/test_sample.py], "
            "implementation: [src/unplanned.py]}\n---\n"
        ),
        "artifacts/tasks/TASK-001.md": (
            "---\nid: TASK-001\nstatus: planned\ndepends_on: [TASK-002]\n"
            "write_files: [tests/test_sample.py]\n---\n"
        ),
        "artifacts/tasks/TASK-002.md": (
            "---\nid: TASK-002\ntype: implementation\nstatus: planned\n"
            "depends_on: [TASK-001]\nrequired_files: []\nwrite_files: []\n---\n"
        ),
        "src/undeclared.py": "val = 1\n",
        "tests/test_sample.py": (
            "from src.domain.models import traces\n"
            "def test_untagged() -> None:\n    return None\n"
            '@traces("REQ-999", "AC-01", "SPEC-999")\n'
            "def test_bad_tag() -> None:\n    return None\n"
        ),
    }
    for relative_path, content in documents.items():
        _write_document(tmp_path / relative_path, content)


@traces("REQ-001", "AC-04", "SPEC-001")
def test_traceability_checker_all_failure_modes(tmp_path: Path) -> None:
    """Verify upstream approval, test contract coverage, and task cycle detection."""
    assert check_traceability(tmp_path)[0].rule_id == "TRACE_POLICY_MISSING"
    _seed_trace_fixtures(tmp_path)
    rules = {
        finding.rule_id
        for finding in [*check_schemas(tmp_path), *check_traceability(tmp_path)]
    }
    assert {
        "TRACE_PATH_GLOB_MISMATCH",
        "TRACE_MISSING_REF",
        "TRACE_UPSTREAM_NOT_APPROVED",
        "TRACE_UNCOVERED_REQ_AC",
        "TRACE_UNTAGGED_TEST",
        "TRACE_INVALID_TAG",
        "TRACE_MISSING_TEST_CONTRACT",
        "TRACE_TASK_CYCLE",
        "TRACE_IMPL_MISSING_TEST_DEP",
        "ARCH_UNDECLARED_TARGET_FILE",
        "TRACE_UNPLANNED_TARGET_FILE",
    }.issubset(rules)
    requirement_stage = {
        finding.rule_id
        for finding in check_traceability(
            tmp_path, ["artifacts/requirements/REQ-002.md"]
        )
    }
    assert "TRACE_UNCOVERED_REQ_AC" not in requirement_stage
    assert "TRACE_MISSING_TEST_CONTRACT" not in requirement_stage
    scoped_target_file = {
        finding.rule_id
        for finding in check_traceability(tmp_path, ["src/undeclared.py"])
    }
    assert "ARCH_UNDECLARED_TARGET_FILE" in scoped_target_file


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


@traces("REQ-001", "AC-03", "SPEC-001")
@traces("REQ-001", "AC-05", "SPEC-001")
def test_output_contract_mypy_and_toggle_sensitivity(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify output_contract formatting, mypy cmd execution, and rule toggles."""
    mypy_command = [
        "python3",
        "-c",
        "import sys; sys.stdout.write('src/a.py:1: err: x\\nsrc/a.py:2: err: y\\n')",
    ]
    clean_configuration: dict[str, Any] = {
        "output_contract": {
            "silent_on_pass": False,
            "finding_format": "{rule_id}|{path}|{line}",
        },
        "remediation": {"CODE_MYPY": "Fix types."},
        "linters": {
            "ruff": {"enabled": False},
            "mypy": {"enabled": True, "cmd": mypy_command},
        },
        "ast_rules": {
            "forbid_todo_fixme_comments": False,
            "forbid_bare_except": False,
            "forbid_pass_only_functions_in_src": False,
            "forbid_print_in_src": False,
            "require_explicit_return_types": False,
        },
    }
    policy_file = tmp_path / "policy" / "clean_code.yaml"
    _write_document(policy_file, yaml.safe_dump(clean_configuration))
    _write_document(
        tmp_path / "src" / "a.py",
        "def stub():\n    try:\n        print(1)\n    except:\n        pass\n",
    )
    assert main(["check", "clean_code", "--root", str(tmp_path)]) == 1
    expected_output = "CODE_MYPY|src/a.py|1 (Hint: Fix types.)\nCODE_MYPY|src/a.py|2"
    assert capsys.readouterr().out.strip() == expected_output
    clean_configuration["linters"]["mypy"]["enabled"] = False
    _write_document(policy_file, yaml.safe_dump(clean_configuration))
    assert main(["check", "clean_code", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out == "OK\n"


@traces("REQ-001", "AC-04", "SPEC-001")
def test_git_commit_traceability_validation(tmp_path: Path) -> None:
    """Verify check_traceability validates Git commit format and referenced IDs."""
    _write_document(
        tmp_path / "policy/traceability.yaml",
        "traceability_rules: {verify_git_commit_traceability: true}\n",
    )
    intent_path = "artifacts/intents/INT-001.md"
    _write_document(tmp_path / intent_path, "---\nid: INT-001\nstatus: open\n---\n")
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    seed_cmd = ["git", "-c", "user.name=mt", "-c", "user.email=mt@local", "commit"]
    subprocess.run(
        [*seed_cmd, "-q", "-m", "INT-001: Seed intent [traces: INT-001]"],
        cwd=tmp_path,
        check=True,
    )
    assert check_traceability(tmp_path) == []
    _write_document(tmp_path / intent_path, "---\nid: INT-001\n---\n")
    commit_traceable_change(
        tmp_path, [intent_path], "INT-001: Bad ref [traces: REQ-999]"
    )
    assert "TRACE_COMMIT_UNKNOWN_ID" in {
        finding.rule_id for finding in check_traceability(tmp_path)
    }
    _write_document(
        tmp_path / intent_path, "---\nid: INT-001\nstatus: processed\n---\n"
    )
    commit_traceable_change(tmp_path, [intent_path], "unformatted")
    assert "TRACE_COMMIT_FORMAT" in {
        finding.rule_id for finding in check_traceability(tmp_path)
    }
