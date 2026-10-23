"""Low-level C and Rust source masking, signature, and variable extraction helpers."""

from dataclasses import dataclass
import re

C_CONTROL_KEYWORDS = {"if", "for", "while", "switch", "return", "sizeof", "catch"}

COMMENT_REGEX = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/")
LITERAL_REGEX = re.compile(r'r#*"[\s\S]*?"#*|"(\\.|[^"\\])*"|\'(\\.|[^\'\\\n])\'')
RUST_FN_REGEX = re.compile(
    r"^[ \t]*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:const\s+)?(?:unsafe\s+)?"
    r"fn\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)"
    r"(?:\s*->\s*(?:\[[^\]]*\]|[^{;])+)?(?:\s+where\s+[^{;]+)?\s*\{",
    re.MULTILINE,
)
C_FN_REGEX = re.compile(
    r"^[ \t]*(?:[a-zA-Z_][a-zA-Z0-9_*\s]+?)\s+\*?([a-zA-Z_][a-zA-Z0-9_]*)"
    r"\s*\(([^;{}]*)\)\s*\{",
    re.MULTILINE,
)
RUST_LET_REGEX = re.compile(r"\blet\s+(?:mut\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\b")
C_VAR_DECL_REGEX = re.compile(
    r"\b(?:(?:const|volatile|static|unsigned|signed|long|short)\s+)*"
    r"(?:int|long|short|char|float|double|bool|_Bool|size_t|ssize_t|ptrdiff_t|"
    r"u?int(?:8|16|32|64|ptr|max)_t|unsigned|signed)\s+\*?\s*"
    r"([a-zA-Z_][a-zA-Z0-9_]*)\s*(?=[=;\[])"
)


@dataclass(frozen=True)
class ParsedFunction:
    """Extracted function metadata for C and Rust source files."""

    name: str
    start_line: int
    end_line: int
    arguments: list[str]
    body_text: str


def line_number_at(source_code: str, offset: int) -> int:
    """Return 1-based line number for a character offset in source_code."""
    return source_code.count("\n", 0, offset) + 1


def blank_preserving_newlines(match: re.Match[str]) -> str:
    """Replace matched non-newline characters with spaces to preserve line numbers."""
    return re.sub(r"[^\n]", " ", match.group(0))


def mask_string_and_character_literals(source_code: str) -> str:
    """Blank C and Rust string and character literals while preserving line numbers."""
    return LITERAL_REGEX.sub(blank_preserving_newlines, source_code)


def mask_comments_and_literals(source_code: str) -> str:
    """Blank C and Rust comments and literals while preserving line numbers."""
    without_literals = mask_string_and_character_literals(source_code)
    return COMMENT_REGEX.sub(blank_preserving_newlines, without_literals)


def _find_closing_brace(masked_code: str, open_brace_index: int) -> int:
    """Find matching closing brace index in masked_code starting at open_brace_index."""
    depth = 0
    for index in range(open_brace_index, len(masked_code)):
        character = masked_code[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(masked_code) - 1


def _strip_nested_delimiters(raw_text: str) -> str:
    """Remove nested <...>, (...), and [...] blocks before splitting parameters."""
    cleaned = raw_text
    for pattern in (r"<[^<>]*>", r"\([^()]*\)", r"\[[^\[\]]*\]"):
        while re.search(pattern, cleaned):
            cleaned = re.sub(pattern, "", cleaned)
    return cleaned


def _parse_arguments(raw_arguments: str, is_rust: bool) -> list[str]:
    """Extract parameter identifier names from a C or Rust parameter list."""
    stripped = _strip_nested_delimiters(raw_arguments.strip())
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
    masked = mask_comments_and_literals(source_code)
    pattern = RUST_FN_REGEX if is_rust else C_FN_REGEX
    functions: list[ParsedFunction] = []
    for match in pattern.finditer(masked):
        name = match.group(1)
        if not is_rust and name in C_CONTROL_KEYWORDS:
            continue
        open_brace = match.end() - 1
        close_brace = _find_closing_brace(masked, open_brace)
        start_line = line_number_at(source_code, match.start())
        end_line = line_number_at(source_code, close_brace)
        arguments = _parse_arguments(match.group(2), is_rust)
        body_text = masked[open_brace + 1 : close_brace].strip()
        functions.append(
            ParsedFunction(name, start_line, end_line, arguments, body_text)
        )
    return functions


def extract_declared_variables(
    masked_code: str, is_rust: bool
) -> list[tuple[str, int]]:
    """Extract local and file-scope variable declarations from masked C/Rust code."""
    pattern = RUST_LET_REGEX if is_rust else C_VAR_DECL_REGEX
    return [
        (match.group(1), line_number_at(masked_code, match.start(1)))
        for match in pattern.finditer(masked_code)
    ]
