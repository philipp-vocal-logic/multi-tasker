"""Clean-repository verification and isolated Git Worktree lifecycle manager."""

import hashlib
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.domain.models import ArtifactDocument, Finding
from multi_tasker.domain.parser import ARTIFACT_DIRECTORY_TO_TYPE, load_yaml_file


def compute_policy_sha256(repository_root: Path) -> str:
    """Compute a deterministic SHA-256 digest over all files in policy/."""
    policy_directory = repository_root / "policy"
    hasher = hashlib.sha256()
    if not policy_directory.exists():
        return hasher.hexdigest()
    for path in sorted(policy_directory.rglob("*")):
        if path.is_file():
            relative_path = path.relative_to(repository_root).as_posix()
            hasher.update(relative_path.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
    return hasher.hexdigest()


def _load_clean_invariants(repository_root: Path) -> dict[str, Any]:
    """Load clean_repo_invariants from policy/permissions.yaml."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    if not permissions_path.exists():
        return {}
    invariants = load_yaml_file(permissions_path).get("clean_repo_invariants", {})
    return invariants if isinstance(invariants, dict) else {}


def verify_clean_repository(
    repository_root: Path, expected_policy_sha256: str | None = None
) -> list[Finding]:
    """Verify BaseBranch working tree is clean and policy/** hash is unchanged."""
    invariants = _load_clean_invariants(repository_root)
    findings: list[Finding] = []
    if invariants.get("require_empty_git_status_before_merge", True):
        for relative_path in get_git_changed_files(repository_root):
            message = (
                f"Repository is not clean; uncommitted change in '{relative_path}'."
            )
            findings.append(Finding(relative_path, 1, "GATE_DIRTY_REPO", message))
    if expected_policy_sha256 is not None and invariants.get(
        "verify_policy_dir_sha256_unchanged", True
    ):
        actual = compute_policy_sha256(repository_root)
        if actual != expected_policy_sha256:
            message = "policy/** SHA-256 digest does not match trusted BaseBranch."
            findings.append(
                Finding("policy/permissions.yaml", 1, "GATE_POLICY_TAMPERED", message)
            )
    return findings


def set_tree_writable(target_directory: Path, writable: bool) -> None:
    """Set or clear write permissions recursively on target_directory."""
    if not target_directory.exists():
        return
    paths = [target_directory, *sorted(target_directory.rglob("*"))]
    for item in paths:
        mode = item.stat().st_mode
        if writable:
            item.chmod(mode | stat.S_IWUSR)
        else:
            item.chmod(mode & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def _has_valid_git_reference(repository_root: Path, base_reference: str) -> bool:
    """Return True if repository_root is a Git repo with a valid base_reference."""
    if not (repository_root / ".git").exists():
        return False
    check = subprocess.run(
        ["git", "rev-parse", "--verify", base_reference],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return check.returncode == 0


def create_worktree(
    repository_root: Path, run_id: str, base_reference: str = "HEAD"
) -> Path:
    """Create an isolated Worktree under .worktrees/<run_id> and lock readonly paths."""
    invariants = _load_clean_invariants(repository_root)
    if invariants.get("require_empty_git_status_before_worktree", True):
        dirty = get_git_changed_files(repository_root)
        if dirty:
            raise RuntimeError(f"Clean repo required before worktree; dirty: {dirty}")
    worktree_path = repository_root / ".worktrees" / run_id
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    if _has_valid_git_reference(repository_root, base_reference):
        subprocess.run(
            ["git", "worktree", "add", "--detach", str(worktree_path), base_reference],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=True,
        )
    else:
        ignored = shutil.ignore_patterns(
            ".worktrees", "__pycache__", ".pytest_cache", ".git", ".report"
        )
        shutil.copytree(repository_root, worktree_path, ignore=ignored)
    for folder in ARTIFACT_DIRECTORY_TO_TYPE:
        (worktree_path / "artifacts" / folder).mkdir(parents=True, exist_ok=True)
    for relative_directory in invariants.get(
        "chmod_readonly_paths_in_worktree", ["policy"]
    ):
        set_tree_writable(worktree_path / str(relative_directory), writable=False)
    return worktree_path


def merge_worktree_files(
    repository_root: Path, worktree_path: Path, relative_paths: list[str]
) -> None:
    """Copy or delete validated changed files from Worktree on BaseBranch."""
    for relative_path in relative_paths:
        source_file = worktree_path / relative_path
        destination_file = repository_root / relative_path
        if source_file.is_file():
            destination_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination_file)
        elif not source_file.exists() and destination_file.is_file():
            destination_file.unlink()


def remove_worktree(repository_root: Path, worktree_path: Path) -> None:
    """Unlock readonly paths and remove an isolated Worktree."""
    if not worktree_path.exists():
        return
    invariants = _load_clean_invariants(repository_root)
    readonly_directories = invariants.get(
        "chmod_readonly_paths_in_worktree", ["policy"]
    )
    for relative_directory in readonly_directories:
        set_tree_writable(worktree_path / str(relative_directory), writable=True)
    if (repository_root / ".git").exists():
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(worktree_path)],
            cwd=repository_root,
            capture_output=True,
            text=True,
            check=False,
        )
    if worktree_path.exists():
        shutil.rmtree(worktree_path, ignore_errors=True)


def format_task_commit_message(document: ArtifactDocument) -> str:
    """Format a deterministic traceable Git commit subject for a Task."""
    task_id = str(document.frontmatter.get("id", "TASK-000"))
    title = str(document.frontmatter.get("title", "Complete task")).strip()
    raw_traces = [str(item) for item in document.frontmatter.get("traces_to", [])]
    traces_csv = ", ".join(raw_traces) if raw_traces else task_id
    return f"{task_id}: {title} [traces: {traces_csv}]"


def commit_traceable_change(
    repository_root: Path, relative_paths: list[str], commit_message: str
) -> bool:
    """Stage relative_paths and create a deterministic Git commit when HEAD exists."""
    if not relative_paths or not _has_valid_git_reference(repository_root, "HEAD"):
        return False
    subprocess.run(
        ["git", "add", "--", *sorted(set(relative_paths))],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    commit_process = subprocess.run(
        [
            "git",
            "-c",
            "user.name=mt-orchestrator",
            "-c",
            "user.email=mt@local",
            "commit",
            "-q",
            "-m",
            commit_message,
        ],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return commit_process.returncode == 0
