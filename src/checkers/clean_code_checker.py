"""Clean code, typing, and KISS/YAGNI checker (`mt check clean_code`)."""

import ast
import io
import re
import shutil
import subprocess
import tokenize
from pathlib import Path
from typing import Any

from src.checkers.common import (
    collect_repository_files,
    format_python_files,
    parse_python_ast,
)
from src.domain.models import Finding
from src.domain.parser import load_yaml_file

RUFF_LINE_REGEX = re.compile(r"^(.+?):(\d+):\d+:\s+([A-Z0-9]+)\s+(.+)$")


def _run_ruff(
    repository_root: Path, targets: list[str], ruff_configuration: dict[str, Any]
) -> list[Finding]:
    """Auto-format targets with ruff format and run ruff check."""
    default_command = ["ruff", "check", "--output-format=concise", "--quiet"]
    base_command = [
        str(part) for part in ruff_configuration.get("cmd", default_command)
    ]
    executable = base_command[0] if base_command else "ruff"
    if (
        not ruff_configuration.get("enabled", True)
        or not shutil.which(executable)
        or not targets
    ):
        return []
    format_python_files(repository_root, targets, ruff_configuration)
    rules = ",".join(
        str(rule) for rule in ruff_configuration.get("select_rules", ["E", "F"])
    )
    max_complexity = int(ruff_configuration.get("max_mccabe_complexity", 8))
    command = [
        *base_command,
        f"--select={rules}",
        "--ignore=ANN401",
        f"--config=lint.mccabe.max-complexity={max_complexity}",
        *targets,
    ]
    process = subprocess.run(
        command, cwd=repository_root, capture_output=True, text=True, check=False
    )
    return [
        Finding(
            Path(match.group(1)).as_posix(),
            int(match.group(2)),
            f"CODE_{match.group(3)}",
            match.group(4),
        )
        for raw_line in process.stdout.splitlines()
        if (match := RUFF_LINE_REGEX.match(raw_line.strip()))
    ]


def _run_mypy(
    repository_root: Path, targets: list[str], mypy_configuration: dict[str, Any]
) -> list[Finding]:
    """Run mypy when enabled and installed in PATH and parse findings."""
    base_command = [str(part) for part in mypy_configuration.get("cmd", ["mypy"])]
    executable = base_command[0] if base_command else "mypy"
    if (
        not mypy_configuration.get("enabled", False)
        or not shutil.which(executable)
        or not targets
    ):
        return []
    command = [*base_command, *targets]
    process = subprocess.run(
        command, cwd=repository_root, capture_output=True, text=True, check=False
    )
    findings: list[Finding] = []
    for raw_line in process.stdout.splitlines():
        parts = raw_line.split(":", maxsplit=3)
        if len(parts) >= 4 and parts[1].strip().isdigit():
            normalized_path = Path(parts[0].strip()).as_posix()
            message = parts[3].strip()
            findings.append(
                Finding(normalized_path, int(parts[1].strip()), "CODE_MYPY", message)
            )
    return findings


def _is_stub_body(body: list[ast.stmt]) -> bool:
    """Return True if function body (excluding docstring) is only pass or ellipsis."""
    statements = body
    if (
        statements
        and isinstance(statements[0], ast.Expr)
        and isinstance(statements[0].value, ast.Constant)
        and isinstance(statements[0].value.value, str)
    ):
        statements = statements[1:]
    if len(statements) != 1:
        return False
    statement = statements[0]
    if isinstance(statement, ast.Pass):
        return True
    return (
        isinstance(statement, ast.Expr)
        and isinstance(statement.value, ast.Constant)
        and statement.value.value is Ellipsis
    )


def _check_function_ast(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    relative_path: str,
    ast_configuration: dict[str, Any],
) -> list[Finding]:
    """Check return type annotation, stub body, and parameter name lengths."""
    findings: list[Finding] = []
    require_return = ast_configuration.get("require_explicit_return_types", True)
    if require_return and node.returns is None:
        message = f"Function '{node.name}' is missing a return type annotation."
        findings.append(
            Finding(relative_path, node.lineno, "CODE_MISSING_RETURN_TYPE", message)
        )
    if (
        ast_configuration.get("forbid_pass_only_functions_in_src", True)
        and relative_path.startswith("src/")
        and _is_stub_body(node.body)
    ):
        message = f"Function '{node.name}' in src/ cannot be a pass/... stub."
        findings.append(
            Finding(relative_path, node.lineno, "CODE_STUB_FUNCTION", message)
        )
    minimum_length = int(ast_configuration.get("min_identifier_length", 3))
    allowed_short = set(ast_configuration.get("allowed_single_char_names", ["_"]))
    for argument in node.args.args:
        if len(argument.arg) < minimum_length and argument.arg not in allowed_short:
            message = (
                f"Argument '{argument.arg}' is shorter than {minimum_length} chars."
            )
            findings.append(
                Finding(relative_path, argument.lineno, "CODE_SHORT_IDENT", message)
            )
    return findings


def _is_forbidden_print(node: ast.AST, relative_path: str, forbid_print: bool) -> bool:
    """Return True if node is a forbidden print() call inside src/."""
    return (
        forbid_print
        and isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "print"
        and relative_path.startswith("src/")
    )


def _check_general_ast(
    tree: ast.AST, relative_path: str, ast_configuration: dict[str, Any]
) -> list[Finding]:
    """Check AST nodes for bare except, print() in src/, short names, and functions."""
    findings: list[Finding] = []
    minimum_length = int(ast_configuration.get("min_identifier_length", 3))
    allowed_short = set(ast_configuration.get("allowed_single_char_names", ["_"]))
    forbid_bare = bool(ast_configuration.get("forbid_bare_except", True))
    forbid_print = bool(ast_configuration.get("forbid_print_in_src", True))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            findings.extend(_check_function_ast(node, relative_path, ast_configuration))
        elif isinstance(node, ast.ExceptHandler) and node.type is None and forbid_bare:
            message = "Bare 'except:' is forbidden."
            findings.append(
                Finding(relative_path, node.lineno, "CODE_BARE_EXCEPT", message)
            )
        elif _is_forbidden_print(node, relative_path, forbid_print):
            message = "Use sys.stdout.write instead of print() in src/."
            line_number = getattr(node, "lineno", 1)
            findings.append(
                Finding(relative_path, line_number, "CODE_PRINT_FORBIDDEN", message)
            )
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and len(node.id) < minimum_length
            and node.id not in allowed_short
        ):
            message = f"Variable '{node.id}' is shorter than {minimum_length} chars."
            findings.append(
                Finding(relative_path, node.lineno, "CODE_SHORT_IDENT", message)
            )
    return findings


def _check_comment_markers(
    source_code: str, relative_path: str, ast_configuration: dict[str, Any]
) -> list[Finding]:
    """Reject forbidden comment markers (e.g., TODO, FIXME, HACK, XXX)."""
    if not ast_configuration.get("forbid_todo_fixme_comments", True):
        return []
    markers = [
        str(marker) for marker in ast_configuration.get("forbidden_comment_markers", [])
    ]
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(marker) for marker in markers) + r")\b"
    )
    findings: list[Finding] = []
    for token in tokenize.generate_tokens(io.StringIO(source_code).readline):
        if token.type == tokenize.COMMENT:
            match = pattern.search(token.string)
            if match:
                message = f"Comment contains forbidden marker '{match.group(1)}'."
                findings.append(
                    Finding(
                        relative_path, token.start[0], "CODE_FORBIDDEN_MARKER", message
                    )
                )
    return findings


def check_clean_code(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/clean_code.yaml across Python source and test files."""
    configuration_path = repository_root / "policy" / "clean_code.yaml"
    if not configuration_path.exists():
        message = "Missing policy/clean_code.yaml."
        return [Finding("policy/clean_code.yaml", 1, "CODE_POLICY_MISSING", message)]
    policy = load_yaml_file(configuration_path)
    python_files = collect_repository_files(
        repository_root, target_paths, ("src", "tests"), {".py"}
    )
    relative_targets = [
        file_path.relative_to(repository_root).as_posix() for file_path in python_files
    ]
    ruff_configuration: dict[str, Any] = policy.get("linters", {}).get("ruff", {})
    mypy_configuration: dict[str, Any] = policy.get("linters", {}).get("mypy", {})
    ast_configuration: dict[str, Any] = policy.get("ast_rules", {})
    findings = _run_ruff(repository_root, relative_targets, ruff_configuration)
    findings.extend(_run_mypy(repository_root, relative_targets, mypy_configuration))
    for absolute_path, relative_path in zip(
        python_files, relative_targets, strict=True
    ):
        source_code = absolute_path.read_text(encoding="utf-8")
        tree, syntax_errors = parse_python_ast(
            source_code, relative_path, "CODE_SYNTAX_ERR"
        )
        if syntax_errors or tree is None:
            findings.extend(syntax_errors)
            continue
        findings.extend(_check_general_ast(tree, relative_path, ast_configuration))
        findings.extend(
            _check_comment_markers(source_code, relative_path, ast_configuration)
        )
    return sorted(set(findings))
