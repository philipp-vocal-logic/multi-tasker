"""Python source code conciseness and sizing checker (`mt check limits`)."""

import ast
import io
import tokenize
from pathlib import Path
from typing import Any

from multi_tasker.checkers.common import (
    collect_repository_files,
    load_source_extensions,
    parse_python_ast,
)
from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import load_yaml_file


def _check_docstring_limits(
    node: ast.AST, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Check docstring line and word limits on a module, class, or function node."""
    docstring_types = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    if not isinstance(node, docstring_types):
        return []
    docstring = ast.get_docstring(node, clean=True)
    if not docstring:
        return []
    line_number = getattr(node, "lineno", 1)
    docstring_lines = len(docstring.splitlines())
    docstring_words = len(docstring.split())
    max_lines = int(source_configuration.get("max_docstring_lines", 3))
    max_words = int(source_configuration.get("max_docstring_words", 35))
    findings: list[Finding] = []
    if docstring_lines > max_lines:
        message = f"Docstring is {docstring_lines} lines (max: {max_lines})."
        findings.append(
            Finding(relative_path, line_number, "LIMIT_DOCSTRING_LINES", message)
        )
    if docstring_words > max_words:
        message = f"Docstring has {docstring_words} words (max: {max_words})."
        findings.append(
            Finding(relative_path, line_number, "LIMIT_DOCSTRING_WORDS", message)
        )
    return findings


def _check_ast_node_limits(
    node: ast.AST, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Check function length/arg limits and class method count limits."""
    findings = _check_docstring_limits(node, relative_path, source_configuration)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        span = getattr(node, "end_lineno", node.lineno) - node.lineno + 1
        max_lines = int(source_configuration.get("max_function_lines", 50))
        if span > max_lines:
            message = f"Function '{node.name}' is {span} lines (max: {max_lines})."
            findings.append(
                Finding(relative_path, node.lineno, "LIMIT_FUNC_LINES", message)
            )
        arguments = [
            item.arg for item in node.args.args if item.arg not in {"self", "cls"}
        ]
        max_arguments = int(source_configuration.get("max_function_args", 6))
        if len(arguments) > max_arguments:
            message = (
                f"Function '{node.name}' has {len(arguments)} "
                f"args (max: {max_arguments})."
            )
            findings.append(
                Finding(relative_path, node.lineno, "LIMIT_FUNC_ARGS", message)
            )
    elif isinstance(node, ast.ClassDef):
        function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
        methods = [item for item in node.body if isinstance(item, function_types)]
        max_methods = int(source_configuration.get("max_class_methods", 10))
        if len(methods) > max_methods:
            message = (
                f"Class '{node.name}' has {len(methods)} methods (max: {max_methods})."
            )
            findings.append(
                Finding(relative_path, node.lineno, "LIMIT_CLASS_METHODS", message)
            )
    return findings


def _check_comment_blocks(
    source_code: str, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Group contiguous inline comments and enforce line and word limits."""
    max_lines = int(source_configuration.get("max_inline_comment_lines", 2))
    max_words = int(source_configuration.get("max_inline_comment_words", 25))
    blocks: list[tuple[int, list[str]]] = []
    previous_line = -2
    for token in tokenize.generate_tokens(io.StringIO(source_code).readline):
        if token.type == tokenize.COMMENT:
            line_number = token.start[0]
            text = token.string.lstrip("#").strip()
            if blocks and line_number == previous_line + 1:
                blocks[-1][1].append(text)
            else:
                blocks.append((line_number, [text]))
            previous_line = line_number
    findings: list[Finding] = []
    for start_line, lines in blocks:
        if len(lines) > max_lines:
            message = f"Inline comment is {len(lines)} lines (max: {max_lines})."
            findings.append(
                Finding(relative_path, start_line, "LIMIT_COMMENT_LEN", message)
            )
        words = len(" ".join(lines).split())
        if words > max_words:
            message = f"Inline comment has {words} words (max: {max_words})."
            findings.append(
                Finding(relative_path, start_line, "LIMIT_COMMENT_WORDS", message)
            )
    return findings


def _check_python_file_limits(
    absolute_path: Path, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce file lines, AST limits, and comment limits on a Python file."""
    source_code = absolute_path.read_text(encoding="utf-8")
    lines = source_code.splitlines()
    max_file_lines = int(source_configuration.get("max_file_lines", 500))
    _ = int(source_configuration.get("refactor_target_file_lines", 400))
    findings: list[Finding] = []
    if len(lines) > max_file_lines:
        message = f"File has {len(lines)} lines (max: {max_file_lines})."
        findings.append(Finding(relative_path, len(lines), "LIMIT_FILE_LINES", message))
    tree, syntax_errors = parse_python_ast(
        source_code, relative_path, "LIMIT_SYNTAX_ERR"
    )
    if syntax_errors or tree is None:
        return [*findings, *syntax_errors]
    for node in ast.walk(tree):
        findings.extend(
            _check_ast_node_limits(node, relative_path, source_configuration)
        )
    findings.extend(
        _check_comment_blocks(source_code, relative_path, source_configuration)
    )
    return findings


def check_limits(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/code_limits.yaml across Python source and test files."""
    limits_path = repository_root / "policy" / "code_limits.yaml"
    if not limits_path.exists():
        message = "Missing policy/code_limits.yaml."
        return [Finding("policy/code_limits.yaml", 1, "LIMIT_POLICY_MISSING", message)]
    policy = load_yaml_file(limits_path)
    source_configuration: dict[str, Any] = policy.get("source_code", {})
    findings: list[Finding] = []
    target_files = collect_repository_files(
        repository_root,
        target_paths,
        ("src", "tests"),
        load_source_extensions(repository_root),
    )
    for absolute_path in target_files:
        relative_path = absolute_path.relative_to(repository_root).as_posix()
        findings.extend(
            _check_python_file_limits(
                absolute_path, relative_path, source_configuration
            )
        )
    return sorted(set(findings))


def collect_refactoring_targets(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Emit non-blocking LIMIT_REFACTOR_HINT Findings for files >400 lines."""
    limits_path = repository_root / "policy" / "code_limits.yaml"
    if not limits_path.exists():
        return []
    source_config: dict[str, Any] = load_yaml_file(limits_path).get("source_code", {})
    refactor_target = int(source_config.get("refactor_target_file_lines", 400))
    max_file_lines = int(source_config.get("max_file_lines", 500))
    hints: list[Finding] = []
    for absolute_path in collect_repository_files(
        repository_root,
        target_paths,
        ("src", "tests"),
        load_source_extensions(repository_root),
    ):
        relative_path = absolute_path.relative_to(repository_root).as_posix()
        line_count = len(absolute_path.read_text(encoding="utf-8").splitlines())
        if refactor_target < line_count <= max_file_lines:
            message = (
                f"File has {line_count} lines "
                f"(refactor target: {refactor_target}, max: {max_file_lines})."
            )
            hints.append(
                Finding(relative_path, line_count, "LIMIT_REFACTOR_HINT", message)
            )
    return sorted(set(hints))
