"""TestContracts for clean_code_checker AST, linter, and output rules."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from multi_tasker.checkers.clean_code_checker import check_clean_code
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces


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
