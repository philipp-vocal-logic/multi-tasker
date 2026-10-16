"""Parallel conflict-free Task scheduler and incremental dirty-flagging engine."""

from pathlib import Path

from src.domain.models import ArtifactDocument
from src.domain.parser import load_artifacts_by_id


def _is_task_eligible(
    repository_root: Path,
    document: ArtifactDocument,
    by_identifier: dict[str, ArtifactDocument],
) -> bool:
    """Return True if Task is planned/ready, deps are done, and required_files exist."""
    if document.frontmatter.get("status") not in {"planned", "ready"}:
        return False
    for dependency_id in document.frontmatter.get("depends_on", []):
        dependency_document = by_identifier.get(str(dependency_id))
        if (
            dependency_document is None
            or dependency_document.frontmatter.get("status") != "done"
        ):
            return False
    for required_file in document.frontmatter.get("required_files", []):
        if not (repository_root / str(required_file)).exists():
            return False
    return True


def select_parallel_batch(
    repository_root: Path, active_write_locks: set[str] | None = None
) -> tuple[list[str], set[str]]:
    """Select a conflict-free batch of eligible Tasks with disjoint WriteScopes."""
    by_identifier = load_artifacts_by_id(repository_root)
    locks = set(active_write_locks) if active_write_locks else set()
    selected: list[str] = []
    tasks = [
        document
        for _, document in sorted(by_identifier.items())
        if document.artifact_type == "TASK"
    ]
    for document in tasks:
        if not _is_task_eligible(repository_root, document, by_identifier):
            continue
        write_set = {
            str(file_path) for file_path in document.frontmatter.get("write_files", [])
        }
        if write_set and write_set.isdisjoint(locks):
            selected.append(str(document.frontmatter["id"]))
            locks.update(write_set)
    return selected, locks


def _references_upstream(document: ArtifactDocument, target_id: str) -> bool:
    """Return True if document links to target_id via traces_to, decisions, etc."""
    frontmatter = document.frontmatter
    for field in ["traces_to", "decisions", "depends_on", "applies_to"]:
        values = frontmatter.get(field, [])
        if isinstance(values, list) and target_id in {str(item) for item in values}:
            return True
    return False


def compute_dirty_subgraph(repository_root: Path, changed_id: str) -> list[str]:
    """Return downstream SPEC and TASK IDs impacted by an update to changed_id."""
    by_identifier = load_artifacts_by_id(repository_root)
    dirty: set[str] = set()
    queue: list[str] = [changed_id]
    while queue:
        current = queue.pop(0)
        for artifact_id, document in sorted(by_identifier.items()):
            if (
                artifact_id not in dirty
                and document.artifact_type in {"SPEC", "TASK"}
                and _references_upstream(document, current)
            ):
                dirty.add(artifact_id)
                queue.append(artifact_id)
    return sorted(dirty)
