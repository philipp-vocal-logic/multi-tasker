"""Architecture layer boundary and import graph checker (`mt check architecture`)."""

import ast
import sys
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from multi_tasker.checkers.common import (
    collect_repository_files,
    load_source_extensions,
    parse_python_ast,
)
from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import load_yaml_file


def _resolve_relative_import(
    relative_path: str, level: int, module: str | None, names: list[ast.alias]
) -> list[str]:
    """Resolve a relative ImportFrom node to dotted module name(s)."""
    package_parts = list(Path(relative_path).parent.parts)
    up_levels = level - 1
    base = package_parts[: max(0, len(package_parts) - up_levels)]
    if module:
        return [".".join([*base, module])]
    return [".".join([*base, alias.name]) for alias in names]


def _extract_imports(tree: ast.AST, relative_path: str = "") -> list[tuple[str, int]]:
    """Extract imported module names (resolving relative imports) and line numbers."""
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0 and relative_path:
                for module_name in _resolve_relative_import(
                    relative_path, node.level, node.module, node.names
                ):
                    imports.append((module_name, node.lineno))
            elif node.module:
                imports.append((node.module, node.lineno))
    return imports


def _find_layer(
    relative_path: str, layers: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Return the layer configuration matching relative_path."""
    for layer in layers:
        if any(fnmatch(relative_path, pattern) for pattern in layer.get("paths", [])):
            return layer
    return None


def _extract_layer_folders(layers: list[dict[str, Any]]) -> tuple[str, ...]:
    """Extract unique top-level folder names from layer path globs."""
    folders = [
        Path(str(pattern)).parts[0]
        for layer in layers
        for pattern in layer.get("paths", [])
        if Path(str(pattern)).parts and "*" not in Path(str(pattern)).parts[0]
    ]
    return tuple(dict.fromkeys([*folders, "src", "tests"]))


def _extract_internal_packages(layers: list[dict[str, Any]]) -> set[str]:
    """Collect top-level internal package names from layer paths and imports."""
    packages = set(_extract_layer_folders(layers))
    for layer in layers:
        for key in ("allowed_internal_imports", "forbidden_internal_imports"):
            for prefix in layer.get(key, []):
                top_name = str(prefix).split(".", maxsplit=1)[0]
                if top_name:
                    packages.add(top_name)
    return packages


def _matches_prefix(module_name: str, prefixes: list[str]) -> bool:
    """Return True if module_name equals or starts with any dotted prefix."""
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in prefixes
    )


def _check_single_import(
    relative_path: str,
    module_name: str,
    line_number: int,
    layer: dict[str, Any],
    context: tuple[set[str], set[str], bool],
) -> Finding | None:
    """Check one import statement against layer rules and third-party allowlist."""
    allowed_packages, internal_packages, no_source_tests = context
    allowed = [str(prefix) for prefix in layer.get("allowed_internal_imports", [])]
    forbidden = [str(prefix) for prefix in layer.get("forbidden_internal_imports", [])]
    layer_name = str(layer.get("name", ""))
    top_package = module_name.split(".", maxsplit=1)[0]
    if no_source_tests and relative_path.startswith("src/") and top_package == "tests":
        message = (
            f"Source file '{relative_path}' cannot import from tests ('{module_name}')."
        )
        return Finding(relative_path, line_number, "ARCH_FORBIDDEN_IMPORT", message)
    if top_package in internal_packages:
        if _matches_prefix(module_name, forbidden) or not _matches_prefix(
            module_name, allowed
        ):
            message = f"Layer '{layer_name}' cannot import '{module_name}'."
            return Finding(relative_path, line_number, "ARCH_FORBIDDEN_IMPORT", message)
        return None
    stdlib_modules = sys.stdlib_module_names
    if top_package not in stdlib_modules and top_package not in allowed_packages:
        message = (
            f"Third-party package '{top_package}' is not in "
            "allowed_third_party_packages."
        )
        return Finding(
            relative_path, line_number, "ARCH_THIRD_PARTY_FORBIDDEN", message
        )
    return None


def _check_file_imports(
    relative_path: str,
    imports: list[tuple[str, int]],
    layer: dict[str, Any] | None,
    package_sets: tuple[set[str], set[str]],
    dependency_rules: dict[str, Any],
) -> list[Finding]:
    """Check a file's imports against layer rules and allowed third-party packages."""
    if layer is None:
        message = f"File '{relative_path}' does not belong to any defined layer."
        return [Finding(relative_path, 1, "ARCH_UNKNOWN_LAYER", message)]
    no_source_tests = bool(dependency_rules.get("forbid_src_importing_tests", True))
    context = (package_sets[0], package_sets[1], no_source_tests)
    findings = [
        _check_single_import(relative_path, module_name, line_number, layer, context)
        for module_name, line_number in imports
    ]
    return [finding for finding in findings if finding is not None]


def _detect_cycles(
    graph: dict[str, set[str]], module_to_path: dict[str, str]
) -> list[Finding]:
    """Detect circular dependencies in the internal module import graph."""
    visited: set[str] = set()
    active: set[str] = set()
    findings: list[Finding] = []

    def depth_first_search(node: str) -> None:
        visited.add(node)
        active.add(node)
        for neighbor in sorted(graph.get(node, set())):
            if neighbor not in visited:
                depth_first_search(neighbor)
            elif neighbor in active:
                path = module_to_path.get(node, node)
                message = f"Circular import detected between '{node}' and '{neighbor}'."
                findings.append(Finding(path, 1, "ARCH_CIRCULAR_IMPORT", message))
        active.remove(node)

    for module_name in sorted(graph):
        if module_name not in visited:
            depth_first_search(module_name)
    return findings


def _path_to_module(relative_path: str) -> str:
    """Convert relative .py path to dotted module name."""
    without_extension = relative_path.removesuffix(".py")
    parts = Path(without_extension).parts
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _extract_graph_edges(
    tree: ast.AST, imports: list[tuple[str, int]], prefixes: tuple[str, ...]
) -> set[str]:
    """Collect internal module targets for circular dependency detection."""
    edges = {imported for imported, _ in imports if imported.startswith(prefixes)}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and not node.level and node.module:
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                if candidate.startswith(prefixes):
                    edges.add(candidate)
    return edges


def _scan_architecture_files(
    repository_root: Path,
    target_paths: list[str] | None,
    layers: list[dict[str, Any]],
    package_sets: tuple[set[str], set[str]],
    rules: dict[str, Any],
) -> tuple[list[Finding], dict[str, set[str]], dict[str, str]]:
    """Scan configured layer files and return findings, import graph, and path map."""
    prefixes = tuple(f"{pkg}." for pkg in sorted(package_sets[1]))
    findings: list[Finding] = []
    graph: dict[str, set[str]] = {}
    module_to_path: dict[str, str] = {}
    for absolute_path in collect_repository_files(
        repository_root,
        target_paths,
        _extract_layer_folders(layers),
        load_source_extensions(repository_root),
    ):
        relative_path = absolute_path.relative_to(repository_root).as_posix()
        source_code = absolute_path.read_text(encoding="utf-8")
        tree, errors = parse_python_ast(source_code, relative_path, "ARCH_SYNTAX_ERR")
        if errors or tree is None:
            findings.extend(errors)
            continue
        imports = _extract_imports(tree, relative_path)
        layer = _find_layer(relative_path, layers)
        findings.extend(
            _check_file_imports(relative_path, imports, layer, package_sets, rules)
        )
        module_name = _path_to_module(relative_path)
        module_to_path[module_name] = relative_path
        graph[module_name] = _extract_graph_edges(tree, imports, prefixes)
    return findings, graph, module_to_path


def check_architecture(
    repository_root: Path, target_paths: list[str] | None = None
) -> list[Finding]:
    """Enforce policy/code_architecture.yaml across configured layer directories."""
    architecture_path = repository_root / "policy" / "code_architecture.yaml"
    if not architecture_path.exists():
        message = "Missing policy/code_architecture.yaml."
        return [
            Finding("policy/code_architecture.yaml", 1, "ARCH_POLICY_MISSING", message)
        ]
    policy = load_yaml_file(architecture_path)
    layers: list[dict[str, Any]] = policy.get("layers", [])
    allowed = {str(pkg) for pkg in policy.get("allowed_third_party_packages", [])}
    internal = _extract_internal_packages(layers)
    rules: dict[str, Any] = policy.get("dependency_rules", {})
    findings, graph, module_to_path = _scan_architecture_files(
        repository_root, target_paths, layers, (allowed, internal), rules
    )
    if rules.get("forbid_circular_imports", True):
        findings.extend(_detect_cycles(graph, module_to_path))
    return sorted(set(findings))
