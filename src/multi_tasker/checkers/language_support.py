"""Multi-language structural rules for ANSI C (.c, .h) and Rust (.rs) checkers."""

from pathlib import Path
import re
from typing import Any

from multi_tasker.checkers.language_parser import (
    COMMENT_REGEX,
    ParsedFunction,
    blank_preserving_newlines,
    extract_c_and_rust_functions,
    extract_declared_variables,
    line_number_at,
    mask_comments_and_literals,
    mask_string_and_character_literals,
)
from multi_tasker.domain.models import Finding

NON_PYTHON_STDLIB = set(
    re.findall(
        r"\w+",
        "assert ctype dirent errno fcntl float inttypes limits locale math "
        "pthread setjmp signal stdarg stdbool stddef stdint stdio stdlib "
        "string sys time unistd std core alloc proc_macro test",
    )
)

C_INCLUDE_LOCAL_REGEX = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
C_INCLUDE_SYS_REGEX = re.compile(r"^\s*#\s*include\s+<([^>]+)>", re.MULTILINE)
RUST_USE_REGEX = re.compile(r"^\s*(?:pub\s+)?use\s+([a-zA-Z0-9_:]+)", re.MULTILINE)
RUST_MOD_PATH_REGEX = re.compile(
    r'^\s*#\s*\[\s*path\s*=\s*"([^"]+)"\s*\]\s*\n\s*(?:pub\s+)?mod\s+([a-zA-Z0-9_]+)',
    re.MULTILINE,
)
TYPE_DECL_REGEX = re.compile(
    r"\b(?:struct|enum|type|union|typedef)\s+([a-zA-Z_][a-zA-Z0-9_]*)\b"
)
CALL_REGEX = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s*!?\s*\(")


def _is_non_python_stub(body_text: str) -> bool:
    """Return True if a C or Rust function body is empty or a todo stub."""
    cleaned = body_text.strip().rstrip(";").strip()
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
    masked_literals = mask_string_and_character_literals(source_code)
    return [
        Finding(
            relative_path,
            line_number_at(source_code, match.start()),
            "CODE_FORBIDDEN_MARKER",
            f"Comment contains forbidden marker '{found.group(1)}'.",
        )
        for match in COMMENT_REGEX.finditer(masked_literals)
        if (found := pattern.search(source_code[match.start() : match.end()]))
    ]


def _check_non_python_short_identifiers(
    masked_code: str,
    relative_path: str,
    functions: list[ParsedFunction],
    ast_configuration: dict[str, Any],
) -> list[Finding]:
    """Check C and Rust parameters and local variables against min_identifier_length."""
    min_len = int(ast_configuration.get("min_identifier_length", 3))
    allowed = set(ast_configuration.get("allowed_single_char_names", ["_"]))
    variables = extract_declared_variables(masked_code, relative_path.endswith(".rs"))
    items = [
        *(
            (arg, func.start_line, "Argument")
            for func in functions
            for arg in func.arguments
        ),
        *((name, line, "Variable") for name, line in variables),
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
    masked = mask_comments_and_literals(source_code)
    functions = extract_c_and_rust_functions(source_code, relative_path)
    findings = [
        *_check_non_python_markers(source_code, relative_path, ast_configuration),
        *_check_non_python_short_identifiers(
            masked, relative_path, functions, ast_configuration
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
                line_number_at(source_code, match.start()),
                "CODE_PRINT_FORBIDDEN",
                f"Call '{match.group(1)}' is forbidden in src/.",
            )
            for match in CALL_REGEX.finditer(masked)
            if match.group(1) in forbidden
        )
    return findings


def _group_non_python_comments(
    source_code: str,
) -> tuple[list[tuple[int, list[str]]], list[tuple[int, list[str]]]]:
    """Group C and Rust comments into (doc_blocks, inline_blocks)."""
    blocks_by_kind: dict[bool, list[tuple[int, list[str]]]] = {True: [], False: []}
    prev_end: dict[bool, int] = {True: -2, False: -2}
    masked_literals = mask_string_and_character_literals(source_code)
    for match in COMMENT_REGEX.finditer(masked_literals):
        raw = source_code[match.start() : match.end()]
        start = line_number_at(source_code, match.start())
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
    masked = mask_comments_and_literals(source_code)
    funcs = extract_c_and_rust_functions(source_code, relative_path)
    return [
        *((func.name, func.start_line) for func in funcs),
        *((arg, func.start_line) for func in funcs for arg in func.arguments),
        *extract_declared_variables(masked, relative_path.endswith(".rs")),
        *(
            (match.group(1), line_number_at(masked, match.start(1)))
            for match in TYPE_DECL_REGEX.finditer(masked)
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


def _resolve_c_include_target(raw_include: str, relative_path: str) -> str:
    """Resolve a local C #include path to a normalized dotted module name."""
    raw_parts = Path(raw_include.removesuffix(".h").removesuffix(".c")).parts
    dotted = ".".join(raw_parts)
    parent_parts = Path(relative_path).parent.parts
    if len(raw_parts) == 1 and len(parent_parts) > 1 and parent_parts[0] == "src":
        return f"{'.'.join(parent_parts)}.{dotted}"
    if dotted.startswith(("src.", "tests.")):
        return dotted
    prefix = "src." if relative_path.startswith("src/") else ""
    return f"{prefix}{dotted}"


def _normalize_rust_use(raw_use: str, current_module: str) -> str:
    """Normalize a Rust use path (crate, super, self) to a dotted module name."""
    dotted = raw_use.replace("::", ".")
    if dotted.startswith("crate."):
        return f"src.{dotted.removeprefix('crate.')}"
    for prefix in ("super", "self"):
        if dotted == prefix or dotted.startswith(f"{prefix}."):
            return f"{current_module}{dotted.removeprefix(prefix)}"
    return dotted


def extract_non_python_imports(
    source_code: str, relative_path: str
) -> list[tuple[str, int]]:
    """Extract normalized dotted imports from C #include or Rust use statements."""
    code_only = COMMENT_REGEX.sub(blank_preserving_newlines, source_code)
    if relative_path.endswith((".c", ".h")):
        local = [
            (
                _resolve_c_include_target(match.group(1), relative_path),
                line_number_at(source_code, match.start()),
            )
            for match in C_INCLUDE_LOCAL_REGEX.finditer(code_only)
        ]
        system = [
            (
                Path(match.group(1).removesuffix(".h")).parts[0],
                line_number_at(source_code, match.start()),
            )
            for match in C_INCLUDE_SYS_REGEX.finditer(code_only)
        ]
        return [*local, *system]
    current_mod = path_to_language_module(relative_path)
    uses = [
        (
            _normalize_rust_use(match.group(1), current_mod),
            line_number_at(source_code, match.start()),
        )
        for match in RUST_USE_REGEX.finditer(code_only)
    ]
    mods = [
        (
            path_to_language_module(match.group(1).lstrip("./")),
            line_number_at(source_code, match.start()),
        )
        for match in RUST_MOD_PATH_REGEX.finditer(code_only)
    ]
    return [*uses, *mods]


def _extract_preceding_annotation_block(
    lines: list[str], start_line: int, min_line: int
) -> str:
    """Collect contiguous comment/attribute lines immediately above start_line."""
    collected: list[str] = []
    for index in range(start_line - 2, max(-1, min_line - 1), -1):
        stripped = lines[index].strip()
        if not stripped or stripped.startswith(("//", "/*", "*", "*/", "#[")):
            collected.append(lines[index])
        else:
            break
    return "\n".join(reversed(collected))


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
    functions = extract_c_and_rust_functions(source_code, relative_path)
    results: list[tuple[str, int, list[tuple[str, str, str]]]] = []
    for index, func in enumerate(functions):
        if not func.name.startswith("test_"):
            continue
        min_line = functions[index - 1].end_line + 1 if index > 0 else 1
        preamble = _extract_preceding_annotation_block(lines, func.start_line, min_line)
        traces_list = pattern.findall(preamble) if argument_count >= 3 else []
        results.append((func.name, func.start_line, traces_list))
    return results
