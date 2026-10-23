"""Reusable checker infrastructure for file discovery, AST parsing, and Git status."""

import ast
from fnmatch import fnmatch
from pathlib import Path
import shutil
import subprocess
from typing import Any

from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import load_yaml_file


def load_ephemeral_globs(repository_root: Path) -> tuple[str, ...]:
    """Load ignored_ephemeral_globs from policy/agent_execution.yaml."""
    execution_path = repository_root / "policy" / "agent_execution.yaml"
    if not execution_path.exists():
        return (".worktrees/**", ".report/**", ".mt_prompt.md")
    invariants = load_yaml_file(execution_path).get("clean_repo_invariants", {})
    raw_globs = (
        invariants.get("ignored_ephemeral_globs", [])
        if isinstance(invariants, dict)
        else []
    )
    return tuple(str(item) for item in raw_globs) or (
        ".worktrees/**",
        ".report/**",
        ".mt_prompt.md",
    )


def load_source_extensions(repository_root: Path) -> set[str]:
    """Load source_extensions from policy/code_quality.yaml."""
    quality_path = repository_root / "policy" / "code_quality.yaml"
    if not quality_path.exists():
        return {".py"}
    policy = load_yaml_file(quality_path)
    _ = policy.get("language", "python")
    extensions = policy.get("source_extensions", [".py"])
    if isinstance(extensions, list) and extensions:
        return {str(item) for item in extensions}
    return {".py"}


def _is_ephemeral_git_entry(entry: str, globs: tuple[str, ...]) -> bool:
    """Return True if a git status path matches any configured ephemeral glob."""
    for pattern in globs:
        normalized = pattern.removeprefix("**/")
        folder_prefix = pattern.removesuffix("/**") + "/"
        if (
            fnmatch(entry, pattern)
            or fnmatch(entry, normalized)
            or entry.startswith(folder_prefix)
            or f"/{normalized.removesuffix('/**')}/" in f"/{entry}/"
        ):
            return True
    return False


def get_git_changed_files(repository_root: Path) -> list[str]:
    """Return modified and untracked relative file paths from git status."""
    ephemeral_globs = load_ephemeral_globs(repository_root)
    if not (repository_root / ".git").exists():
        return []
    head_process = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if head_process.returncode != 0:
        return []
    status_process = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if status_process.returncode != 0:
        return []
    paths: list[str] = []
    for raw_line in status_process.stdout.splitlines():
        if len(raw_line) > 3:
            entry = raw_line[3:].strip()
            if " -> " in entry:
                entry = entry.split(" -> ", maxsplit=1)[1].strip()
            if not _is_ephemeral_git_entry(entry, ephemeral_globs):
                paths.append(entry)
    return sorted(set(paths))


def get_git_commit_subjects(repository_root: Path) -> list[tuple[str, str]]:
    """Return (short_hash, subject) pairs from git log when HEAD exists."""
    if not (repository_root / ".git").exists():
        return []
    log_process = subprocess.run(
        ["git", "log", "--format=%h%x09%s"],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if log_process.returncode != 0:
        return []
    commits: list[tuple[str, str]] = []
    for raw_line in log_process.stdout.splitlines():
        if "\t" in raw_line:
            commit_hash, subject = raw_line.split("\t", maxsplit=1)
            commits.append((commit_hash.strip(), subject.strip()))
    return commits


def get_git_commit_files(repository_root: Path, commit_hash: str) -> list[str]:
    """Return modified relative file paths in a specific Git commit."""
    process = subprocess.run(
        ["git", "show", "--pretty=format:", "--name-only", commit_hash],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        return []
    return [line.strip() for line in process.stdout.splitlines() if line.strip()]


def collect_repository_files(
    repository_root: Path,
    target_paths: list[str] | None,
    folders: tuple[str, ...],
    suffixes: set[str],
    require_folder_prefix: bool = False,
) -> list[Path]:
    """Collect matching repository files from target_paths or default folders."""
    if target_paths:
        prefixes = tuple(f"{folder}/" for folder in folders)
        return [
            repository_root / relative_path
            for relative_path in target_paths
            if Path(relative_path).suffix in suffixes
            and (not require_folder_prefix or relative_path.startswith(prefixes))
            and (repository_root / relative_path).is_file()
        ]
    collected_files: list[Path] = []
    for folder in folders:
        base_directory = repository_root / folder
        if base_directory.exists():
            matched = [
                file_path
                for file_path in base_directory.rglob("*")
                if file_path.is_file() and file_path.suffix in suffixes
            ]
            collected_files.extend(sorted(matched))
    return collected_files


def parse_python_ast(
    source_code: str, relative_path: str, syntax_rule_id: str
) -> tuple[ast.AST | None, list[Finding]]:
    """Parse Python source into an AST or return a syntax-error Finding."""
    try:
        return ast.parse(source_code, filename=relative_path), []
    except SyntaxError as error:
        message = f"Syntax error: {error.msg}"
        finding = Finding(relative_path, error.lineno or 1, syntax_rule_id, message)
        return None, [finding]


def format_python_files(
    repository_root: Path,
    targets: list[str],
    ruff_configuration: dict[str, Any],
) -> list[Finding]:
    """Format target Python files in-place using ruff format when enabled."""
    format_command = [
        str(part)
        for part in ruff_configuration.get("format_cmd", ["ruff", "format", "--quiet"])
    ]
    executable = format_command[0] if format_command else "ruff"
    if not targets or not ruff_configuration.get("enabled", True):
        return []
    if not shutil.which(executable):
        message = f"Linter executable '{executable}' not found in PATH."
        return [Finding("policy/code_quality.yaml", 1, "CODE_LINTER_MISSING", message)]
    process = subprocess.run(
        [*format_command, *targets],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        lines = (process.stderr or process.stdout).strip().splitlines()
        detail = lines[-1] if lines else f"ruff format exited {process.returncode}."
        return [Finding("policy/code_quality.yaml", 1, "CODE_RUFF", detail)]
    return []


def extract_test_traces(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    decorator_name: str = "traces",
    argument_count: int = 3,
) -> list[tuple[str, str, str]]:
    """Extract (requirement_id, criterion_id, specification_id) from decorators."""
    tags: list[tuple[str, str, str]] = []
    for decorator in function_node.decorator_list:
        if isinstance(decorator, ast.Call):
            function = decorator.func
            name = (
                function.id
                if isinstance(function, ast.Name)
                else getattr(function, "attr", "")
            )
            if name == decorator_name and len(decorator.args) == argument_count >= 3:
                values = [
                    argument.value
                    if isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    else ""
                    for argument in decorator.args
                ]
                if all(values):
                    tags.append((values[0], values[1], values[2]))
    return tags


class TrackedPolicyDict(dict[str, Any]):
    """Dictionary wrapper recording every policy key read by checkers."""

    def __init__(self, data: dict[str, Any], log: set[str]) -> None:
        """Initialize wrapped mapping and shared key access log."""
        super().__init__({key: _wrap_node(value, log) for key, value in data.items()})
        self._log = log

    def get(self, key: str, default: Any = None) -> Any:
        """Record key lookup and return wrapped value or default."""
        self._log.add(str(key))
        return super().get(key, default)

    def __getitem__(self, key: str) -> Any:
        """Record key indexing and return wrapped value."""
        self._log.add(str(key))
        return super().__getitem__(key)

    def items(self) -> Any:
        """Record all keys when iterating over key-value pairs."""
        self._log.update(str(key) for key in self.keys())
        return super().items()


def _wrap_node(value: Any, log: set[str]) -> Any:
    """Recursively wrap dicts and lists in TrackedPolicyDict."""
    if isinstance(value, dict):
        return TrackedPolicyDict(value, log)
    if isinstance(value, list):
        return [_wrap_node(item, log) for item in value]
    return value


def collect_policy_keys(node: Any) -> set[str]:
    """Collect all dictionary keys in a policy structure outside json_schema."""
    if isinstance(node, dict):
        sub_keys = (
            collect_policy_keys(value)
            for key, value in node.items()
            if key != "json_schema"
        )
        return {*(str(key) for key in node), *set().union(*sub_keys)}
    if isinstance(node, list):
        return set().union(*(collect_policy_keys(item) for item in node))
    return set()
