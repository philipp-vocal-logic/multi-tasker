"""Glossary and canonical vocabulary checker (`mt check glossary`)."""

import ast
import re
from pathlib import Path
from typing import Any

from multi_tasker.checkers.common import collect_repository_files, parse_python_ast
from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import load_yaml_file

WORD_TOKEN_REGEX = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|[A-Z]?[a-z]+|\d+")
SynonymRule = tuple[re.Pattern[str], tuple[str, ...], str, str, str]


def _split_words(text: str) -> tuple[str, ...]:
    """Split CamelCase, snake_case, or phrase into lowercase word tokens."""
    return tuple(token.lower() for token in WORD_TOKEN_REGEX.findall(text))


def _matches_synonym_tokens(
    identifier_tokens: tuple[str, ...],
    synonym_tokens: tuple[str, ...],
    synonym_compact: str,
) -> bool:
    """Return True if identifier_tokens contains synonym_tokens or compound."""
    if not identifier_tokens or not synonym_tokens:
        return False
    span = len(synonym_tokens)
    if any(
        identifier_tokens[index : index + span] == synonym_tokens
        for index in range(len(identifier_tokens) - span + 1)
    ):
        return True
    return span > 1 and synonym_compact in identifier_tokens


def _build_synonym_rules(terms: list[dict[str, Any]]) -> list[SynonymRule]:
    """Compile regex and word-token rules for non-allowed forbidden_synonyms."""
    rules: list[SynonymRule] = []
    for entry in terms:
        canonical = str(entry.get("canonical", ""))
        allowed = {str(form).lower() for form in entry.get("allowed_forms", [])}
        for synonym in entry.get("forbidden_synonyms", []):
            synonym_string = str(synonym)
            if synonym_string.lower() not in allowed:
                pattern = re.compile(rf"\b{re.escape(synonym_string)}\b", re.IGNORECASE)
                tokens = _split_words(synonym_string)
                rules.append(
                    (pattern, tokens, "".join(tokens), synonym_string, canonical)
                )
    return rules


def _check_markdown_file(
    absolute_path: Path, relative_path: str, rules: list[SynonymRule]
) -> list[Finding]:
    """Scan Markdown lines outside fenced code blocks for forbidden synonyms."""
    findings: list[Finding] = []
    in_fence = False
    raw_lines = absolute_path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(raw_lines, start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line_tokens = _split_words(line)
        for pattern, tokens, compact, synonym_string, canonical in rules:
            if pattern.search(line) or _matches_synonym_tokens(
                line_tokens, tokens, compact
            ):
                message = (
                    f"Term '{synonym_string}' is forbidden; "
                    f"use canonical term '{canonical}'."
                )
                findings.append(
                    Finding(relative_path, line_number, "GLOSSARY_FORBIDDEN", message)
                )
    return findings


def _check_file_name(relative_path: str, rules: list[SynonymRule]) -> list[Finding]:
    """Verify file path tokens do not contain forbidden synonyms."""
    path_tokens = _split_words(relative_path)
    findings: list[Finding] = []
    for _, tokens, compact, synonym_string, canonical in rules:
        if _matches_synonym_tokens(path_tokens, tokens, compact):
            message = (
                f"File path '{relative_path}' contains forbidden term "
                f"'{synonym_string}'; use '{canonical}'."
            )
            findings.append(
                Finding(relative_path, 1, "GLOSSARY_FORBIDDEN_FILE", message)
            )
    return findings


def _extract_ast_identifiers(tree: ast.AST) -> list[tuple[str, int]]:
    """Collect defined class, function, argument, and target identifiers."""
    items: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            items.append((node.name, node.lineno))
        elif isinstance(node, ast.arg):
            items.append((node.arg, node.lineno))
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            items.append((node.id, node.lineno))
    return items


def _check_identifier_casing(
    relative_path: str,
    identifier_items: list[tuple[str, int]],
    terms: list[dict[str, Any]],
) -> list[Finding]:
    """Verify Python AST identifiers match canonical or code_identifiers casing."""
    allowed_by_lower: dict[str, set[str]] = {}
    for entry in terms:
        canonical = str(entry.get("canonical", ""))
        code_identifiers = [str(item) for item in entry.get("code_identifiers", [])]
        for form in {canonical, *code_identifiers}:
            if form:
                allowed_by_lower.setdefault(form.lower(), set()).add(form)
    findings: list[Finding] = []
    for identifier, line_number in identifier_items:
        lower_identifier = identifier.lower()
        if (
            lower_identifier in allowed_by_lower
            and identifier not in allowed_by_lower[lower_identifier]
        ):
            expected = min(allowed_by_lower[lower_identifier])
            message = (
                f"Identifier '{identifier}' mismatches glossary casing '{expected}'."
            )
            findings.append(
                Finding(relative_path, line_number, "GLOSSARY_CASE_MISMATCH", message)
            )
    return findings


def _check_identifier_synonyms(
    relative_path: str,
    identifier_items: list[tuple[str, int]],
    terms: list[dict[str, Any]],
) -> list[Finding]:
    """Verify Python AST identifiers do not contain forbidden synonym tokens."""
    rules = _build_synonym_rules(terms)
    findings: list[Finding] = []
    for identifier, line_number in identifier_items:
        identifier_tokens = _split_words(identifier)
        for _, tokens, compact, synonym_string, canonical in rules:
            if _matches_synonym_tokens(identifier_tokens, tokens, compact):
                message = (
                    f"Identifier '{identifier}' contains forbidden term "
                    f"'{synonym_string}'; use '{canonical}'."
                )
                findings.append(
                    Finding(
                        relative_path, line_number, "GLOSSARY_FORBIDDEN_IDENT", message
                    )
                )
    return findings


def _check_python_identifiers(
    absolute_path: Path,
    relative_path: str,
    terms: list[dict[str, Any]],
    enforcement: dict[str, Any],
) -> list[Finding]:
    """Verify Python AST identifiers against forbidden synonyms and casing."""
    source_code = absolute_path.read_text(encoding="utf-8")
    tree, syntax_errors = parse_python_ast(
        source_code, relative_path, "GLOSSARY_SYNTAX_ERR"
    )
    if syntax_errors or tree is None:
        return syntax_errors
    identifier_items = _extract_ast_identifiers(tree)
    findings: list[Finding] = []
    if enforcement.get("fail_on_forbidden_synonym", True):
        findings.extend(
            _check_identifier_synonyms(relative_path, identifier_items, terms)
        )
    if enforcement.get("fail_on_identifier_case_mismatch", True):
        findings.extend(
            _check_identifier_casing(relative_path, identifier_items, terms)
        )
    return findings


def check_glossary(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/glossary.yaml across artifacts, file names, and identifiers."""
    glossary_path = repository_root / "policy" / "glossary.yaml"
    if not glossary_path.exists():
        message = "Missing policy/glossary.yaml."
        return [Finding("policy/glossary.yaml", 1, "GLOSSARY_POLICY_MISSING", message)]
    policy = load_yaml_file(glossary_path)
    terms: list[dict[str, Any]] = policy.get("terms", [])
    enforcement: dict[str, Any] = policy.get("enforcement", {})
    rules = (
        _build_synonym_rules(terms)
        if enforcement.get("fail_on_forbidden_synonym", True)
        else []
    )
    findings: list[Finding] = []
    target_files = collect_repository_files(
        repository_root, target_paths, ("artifacts", "src", "tests"), {".md", ".py"}
    )
    for absolute_path in target_files:
        relative_path = absolute_path.relative_to(repository_root).as_posix()
        if enforcement.get("check_file_names", True):
            findings.extend(_check_file_name(relative_path, rules))
        if absolute_path.suffix == ".md" and enforcement.get(
            "check_markdown_prose", True
        ):
            findings.extend(_check_markdown_file(absolute_path, relative_path, rules))
        elif absolute_path.suffix == ".py" and enforcement.get(
            "check_code_identifiers", True
        ):
            findings.extend(
                _check_python_identifiers(
                    absolute_path, relative_path, terms, enforcement
                )
            )
    return sorted(set(findings))
