"""Multi-language structural parser for ANSI C (.c, .h) and Rust (.rs) checkers."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

from multi_tasker.domain.models import Finding

NON_PYTHON_STDLIB = set(
    re.findall(
        r"\w+",
        "assert ctype errno float limits locale math setjmp signal stdarg "
        "stdbool stddef stdint stdio stdlib string time std core alloc proc_macro test",
    )
)
C_CONTROL_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "catch"}

COMMENT_REGEX = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/")
C_INCLUDE_LOCAL_REGEX = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
C_INCLUDE_SYS_REGEX = re.compile(r"^\s*#\s*include\s+<([^>]+)>", re.MULTILINE)
RUST_USE_REGEX = re.compile(r"^\s*(?:pub\s+)?use\s+([a-zA-Z0-9_:]+)", re.MULTILINE)
RUST_MOD_PATH_REGEX = re.compile(
    r'^\s*#\s*\[\s*path\s*=\s*"([^"]+)"\s*\]\s*\n\s*(?:pub\s+)?mod\s+([a-zA-Z0-9_]+)',
    re.MULTILINE,
)
RUST_FN_REGEX = re.compile(
    r"^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:const\s+)?(?:unsafe\s+)?"
    r"fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
    r"(?:\s*->\s*[^{;]+)?\s*\{",
    re.MULTILINE,
)
C_FN_REGEX = re.compile(
    r"^[ \t]*(?:[a-zA-Z_][a-zA-Z0-9_*\s]+?)\s+\*?([a-zA-Z_][a-zA-Z0-9_]*)"
    r"\s*\(([^;{}]*)\)\s*\{",
    re.MULTILINE,
)
VAR_DECL_REGEX = re.compile(
    r"\b(?:let\s+(?:mut\s+)?|int\s+|long\s+|short\s+|char\s+|float\s+|double\s+|"
    r"unsigned\s+|size_t\s+)([a-zA-Z_][a-zA-Z0-9_]*)\b"
)
TYPE_DECL_REGEX = re.compile(
    r"\b(?:struct|enum|type|union|typedef)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b"
)
CALL_REGEX = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*!?\s*\(")


@dataclass(frozen=True)
class ParsedFunction:
    """Extracted function metadata for C and Rust source files."""

    name: str
    start_line: int
    end_line: int
    arguments: list[str]
    body_text: str


def _line_number_at(source_code: str, offset: int) -> int:
    """Return 1-based line number for a character offset in source_code."""
    return source_code.count("\n", 0, offset) + 1


def _find_closing_brace(source_code: str, open_brace_index: int) -> int:
    """Find matching closing brace index starting from open_brace_index."""
    depth = 0
    for index in range(open_brace_index, len(source_code)):
        character = source_code[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(source_code) - 1


def _parse_arguments(raw_arguments: str, is_rust: bool) -> list[str]:
    """Extract parameter identifier names from a C or Rust parameter list."""
    stripped = raw_arguments.strip()
    if not stripped or (not is_rust and stripped == "void"):
        return []
    names: list[str] = []
    for part in stripped.split(","):
        cleaned = part.strip()
        if not cleaned or cleaned in {"self", "&self", "&mut self", "mut self"}:
            continue
        target = cleaned.split(":", maxsplit=1)[0].strip() if is_rust else cleaned
        tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", target)
        if tokens:
            names.append(tokens[-1])
    return names


def extract_c_and_rust_functions(
    source_code: str, relative_path: str
) -> list[ParsedFunction]:
    """Extract function spans, arguments, and bodies from a C or Rust file."""
    is_rust = relative_path.endswith(".rs")
    pattern = RUST_FN_REGEX if is_rust else C_FN_REGEX
    functions: list[ParsedFunction] = []
    for match in pattern.finditer(source_code):
        name = match.group(1)
        if not is_rust and name in C_CONTROL_KEYWORDS:
            continue
        open_brace = match.end() - 1
        close_brace = _find_closing_brace(source_code, open_brace)
        start_line = _line_number_at(source_code, match.start())
        end_line = _line_number_at(source_code, close_brace)
        arguments = _parse_arguments(match.group(2), is_rust)
        body_text = source_code[open_brace + 1 : close_brace].strip()
        functions.append(
            ParsedFunction(name, start_line, end_line, arguments, body_text)
        )
    return functions


def _is_non_python_stub(body_text: str) -> bool:
    """Return True if a C or Rust function body is empty or a todo stub."""
    cleaned = COMMENT_REGEX.sub("", body_text).strip().rstrip(";").strip()
    return not cleaned or cleaned.startswith(("todo!(", "unimplemented!("))


def _check_non_python_markers(
    source_code: str, relative_path: str, ast_configuration: dict[str, Any]
) -> list[Finding]:
    """Check C and Rust comments for forbidden markers (TODO, FIXME, etc.)."""
    if not ast_configuration.get("forbid_todo_fixme_comments", True):
        return []
    markers = [
        str(item) for item in ast_configuration.get("forbidden_comment_markers", [])
    ]
    if not markers:
        return []
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(item) for item in markers) + r")\b"
    )
    return [
        Finding(
            relative_path,
            _line_number_at(source_code, match.start()),
            "CODE_FORBIDDEN_MARKER",
            f"Comment contains forbidden marker '{found.group(1)}'.",
        )
        for match in COMMENT_REGEX.finditer(source_code)
        if (found := pattern.search(match.group(0)))
    ]


def _check_non_python_short_identifiers(
    source_code: str,
    relative_path: str,
    functions: list[ParsedFunction],
    ast_configuration: dict[str, Any],
) -> list[Finding]:
    """Check C and Rust parameters and local variables against min_identifier_length."""
    min_len = int(ast_configuration.get("min_identifier_length", 3))
    allowed = set(ast_configuration.get("allowed_single_char_names", ["_"]))
    items = [
        *(
            (arg, func.start_line, "Argument")
            for func in functions
            for arg in func.arguments
        ),
        *(
            (match.group(1), _line_number_at(source_code, match.start()), "Variable")
            for match in VAR_DECL_REGEX.finditer(source_code)
        ),
    ]
    return [
        Finding(
            relative_path,
            line,
            "CODE_SHORT_IDENT",
            f"{kind} '{name}' is shorter than {min_len} chars.",
        )
        for name, line, kind in items
        if len(name) < min_len and name not in allowed
    ]


def check_non_python_clean_code(
    source_code: str, relative_path: str, ast_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce clean_code AST rules on ANSI C (.c, .h) and Rust (.rs) files."""
    functions = extract_c_and_rust_functions(source_code, relative_path)
    findings = [
        *_check_non_python_markers(source_code, relative_path, ast_configuration),
        *_check_non_python_short_identifiers(
            source_code, relative_path, functions, ast_configuration
        ),
    ]
    if ast_configuration.get(
        "forbid_pass_only_functions_in_src", True
    ) and relative_path.startswith("src/"):
        findings.extend(
            Finding(
                relative_path,
                func.start_line,
                "CODE_STUB_FUNCTION",
                f"Function '{func.name}' in src/ cannot be an empty/todo stub.",
            )
            for func in functions
            if _is_non_python_stub(func.body_text)
        )
    forbidden = {
        str(item).rstrip("!")
        for item in ast_configuration.get("forbidden_calls_in_src", [])
    }
    if forbidden and relative_path.startswith("src/"):
        findings.extend(
            Finding(
                relative_path,
                _line_number_at(source_code, match.start()),
                "CODE_PRINT_FORBIDDEN",
                f"Call '{match.group(1)}' is forbidden in src/.",
            )
            for match in CALL_REGEX.finditer(source_code)
            if match.group(1) in forbidden
        )
    return findings


def _group_non_python_comments(
    source_code: str,
) -> tuple[list[tuple[int, list[str]]], list[tuple[int, list[str]]]]:
    """Group C and Rust comments into (doc_blocks, inline_blocks)."""
    blocks_by_kind: dict[bool, list[tuple[int, list[str]]]] = {True: [], False: []}
    prev_end: dict[bool, int] = {True: -2, False: -2}
    for match in COMMENT_REGEX.finditer(source_code):
        raw = match.group(0)
        start = _line_number_at(source_code, match.start())
        cleaned = [
            stripped
            for line in raw.splitlines()
            if (stripped := re.sub(r"^[/*!\s]+|[*/\s]+$", "", line))
        ]
        if not cleaned:
            continue
        is_doc = raw.startswith(("/**", "//!", "///"))
        if blocks_by_kind[is_doc] and start == prev_end[is_doc] + 1:
            blocks_by_kind[is_doc][-1][1].extend(cleaned)
        else:
            blocks_by_kind[is_doc].append((start, cleaned))
        prev_end[is_doc] = start + len(raw.splitlines()) - 1
    return blocks_by_kind[True], blocks_by_kind[False]


def _check_non_python_comment_limits(
    source_code: str, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce doc comment and inline comment line/word limits on C and Rust files."""
    doc_blocks, inline_blocks = _group_non_python_comments(source_code)
    checks = [
        (
            doc_blocks,
            int(source_configuration.get("max_docstring_lines", 3)),
            int(source_configuration.get("max_docstring_words", 35)),
            "LIMIT_DOCSTRING_LINES",
            "LIMIT_DOCSTRING_WORDS",
            "Docstring",
        ),
        (
            inline_blocks,
            int(source_configuration.get("max_inline_comment_lines", 2)),
            int(source_configuration.get("max_inline_comment_words", 25)),
            "LIMIT_COMMENT_LEN",
            "LIMIT_COMMENT_WORDS",
            "Inline comment",
        ),
    ]
    findings: list[Finding] = []
    for blocks, max_lines, max_words, line_rule, word_rule, label in checks:
        for line_no, lines in blocks:
            if len(lines) > max_lines:
                msg = f"{label} is {len(lines)} lines (max: {max_lines})."
                findings.append(Finding(relative_path, line_no, line_rule, msg))
            words = len(" ".join(lines).split())
            if words > max_words:
                msg = f"{label} has {words} words (max: {max_words})."
                findings.append(Finding(relative_path, line_no, word_rule, msg))
    return findings


def check_non_python_file_limits(
    source_code: str, relative_path: str, source_configuration: dict[str, Any]
) -> list[Finding]:
    """Enforce file, function, docstring, and inline comment limits on C/Rust files."""
    line_count = len(source_code.splitlines())
    max_file = int(source_configuration.get("max_file_lines", 500))
    max_fn = int(source_configuration.get("max_function_lines", 50))
    max_args = int(source_configuration.get("max_function_args", 6))
    findings: list[Finding] = []
    if line_count > max_file:
        msg = f"File has {line_count} lines (max: {max_file})."
        findings.append(Finding(relative_path, line_count, "LIMIT_FILE_LINES", msg))
    for func in extract_c_and_rust_functions(source_code, relative_path):
        span = func.end_line - func.start_line + 1
        if span > max_fn:
            msg = f"Function '{func.name}' is {span} lines (max: {max_fn})."
            findings.append(
                Finding(relative_path, func.start_line, "LIMIT_FUNC_LINES", msg)
            )
        if len(func.arguments) > max_args:
            cnt = len(func.arguments)
            msg = f"Function '{func.name}' has {cnt} args (max: {max_args})."
            findings.append(
                Finding(relative_path, func.start_line, "LIMIT_FUNC_ARGS", msg)
            )
    return [
        *findings,
        *_check_non_python_comment_limits(
            source_code, relative_path, source_configuration
        ),
    ]


def extract_non_python_identifiers(
    source_code: str, relative_path: str
) -> list[tuple[str, int]]:
    """Extract function, parameter, variable, and type identifiers from C/Rust code."""
    funcs = extract_c_and_rust_functions(source_code, relative_path)
    return [
        *((func.name, func.start_line) for func in funcs),
        *((arg, func.start_line) for func in funcs for arg in func.arguments),
        *(
            (match.group(1), _line_number_at(source_code, match.start()))
            for regex in (VAR_DECL_REGEX, TYPE_DECL_REGEX)
            for match in regex.finditer(source_code)
        ),
    ]


def path_to_language_module(relative_path: str) -> str:
    """Convert a .py, .c, .h, or .rs relative path into a dotted module identifier."""
    for suffix in (".py", ".rs", ".c", ".h"):
        if relative_path.endswith(suffix):
            parts = Path(relative_path.removesuffix(suffix)).parts
            if parts and parts[-1] in {"__init__", "mod", "lib"}:
                parts = parts[:-1]
            return ".".join(parts)
    return ".".join(Path(relative_path).parts)


def extract_non_python_imports(
    source_code: str, relative_path: str
) -> list[tuple[str, int]]:
    """Extract normalized dotted imports from C #include or Rust use statements."""
    imports: list[tuple[str, int]] = []
    prefix = "src." if relative_path.startswith("src/") else ""
    if relative_path.endswith((".c", ".h")):
        for match in C_INCLUDE_LOCAL_REGEX.finditer(source_code):
            dotted = ".".join(
                Path(match.group(1).removesuffix(".h").removesuffix(".c")).parts
            )
            target = (
                dotted if dotted.startswith(("src.", "tests.")) else f"{prefix}{dotted}"
            )
            imports.append((target, _line_number_at(source_code, match.start())))
        for match in C_INCLUDE_SYS_REGEX.finditer(source_code):
            sys_header = Path(match.group(1).removesuffix(".h")).parts[0]
            imports.append((sys_header, _line_number_at(source_code, match.start())))
        return imports
    for match in RUST_USE_REGEX.finditer(source_code):
        raw_use = match.group(1).replace("::", ".")
        if raw_use.startswith("crate."):
            raw_use = f"src.{raw_use.removeprefix('crate.')}"
        imports.append((raw_use, _line_number_at(source_code, match.start())))
    for match in RUST_MOD_PATH_REGEX.finditer(source_code):
        mod_target = path_to_language_module(match.group(1).lstrip("./"))
        imports.append((mod_target, _line_number_at(source_code, match.start())))
    return imports


def extract_non_python_test_functions(
    source_code: str,
    relative_path: str = ".c",
    decorator_name: str = "traces",
    argument_count: int = 3,
) -> list[tuple[str, int, list[tuple[str, str, str]]]]:
    """Extract test_* functions and preceding @traces annotations from C/Rust files."""
    pattern = re.compile(
        rf'@?{re.escape(decorator_name)}\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)'
    )
    lines = source_code.splitlines()
    return [
        (
            func.name,
            func.start_line,
            pattern.findall(
                "\n".join(lines[max(0, func.start_line - 6) : func.start_line])
            )
            if argument_count >= 3
            else [],
        )
        for func in extract_c_and_rust_functions(source_code, relative_path)
        if func.name.startswith("test_")
    ]
