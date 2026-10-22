"""Bidirectional Traceability lineage inspection (`mt trace`) and coverage metrics."""

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from multi_tasker.checkers.common import (
    extract_test_traces,
    get_git_commit_subjects,
    parse_python_ast,
)
from multi_tasker.domain.models import ArtifactDocument
from multi_tasker.domain.parser import load_artifacts_by_id

COMMIT_ID_REGEX = re.compile(r"\b(?:INT|REQ|SPEC|TASK|ESC|DEC|REV)-[0-9]{3,}\b")

_COVERAGE_RUNNER_SCRIPT = (
    "import json, sys, pytest\n"
    "from pathlib import Path\n"
    "src = str((Path.cwd() / 'src').resolve())\n"
    "hit = {}\n"
    "mon = sys.monitoring\n"
    "mon.use_tool_id(4, 'mt_cov')\n"
    "mon.register_callback(4, mon.events.PY_START, lambda c, o: "
    "mon.set_local_events(4, c, mon.events.LINE) "
    "if c.co_filename.startswith(src) else mon.DISABLE)\n"
    "mon.register_callback(4, mon.events.LINE, lambda c, ln: "
    "(hit.setdefault(c.co_filename, set()).add(ln), mon.DISABLE)[1])\n"
    "mon.set_events(4, mon.events.PY_START)\n"
    "try:\n"
    "    rc = int(pytest.main(['-q', 'tests']))\n"
    "finally:\n"
    "    mon.set_events(4, 0)\n"
    "    mon.free_tool_id(4)\n"
    "out = {'exit_code': rc, 'hit': {k: sorted(v) for k, v in hit.items()}}\n"
    "Path('.report/raw_coverage.json').write_text(json.dumps(out), encoding='utf-8')\n"
)


def _extract_function_trace_links(
    node: ast.AST, relative_path: str
) -> list[tuple[str, str, str, str]]:
    """Extract (requirement_id, criterion_id, specification_id, location) from AST."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    location = f"{relative_path}:{node.name}"
    return [
        (req_id, criterion_id, spec_id, location)
        for req_id, criterion_id, spec_id in extract_test_traces(node)
    ]


def collect_test_trace_links(
    repository_root: Path,
) -> list[tuple[str, str, str, str]]:
    """Collect (requirement_id, criterion_id, specification_id, location) in tests/."""
    test_directory = repository_root / "tests"
    if not test_directory.exists():
        return []
    entries: list[tuple[str, str, str, str]] = []
    for python_path in sorted(test_directory.rglob("test_*.py")):
        relative_path = python_path.relative_to(repository_root).as_posix()
        source_code = python_path.read_text(encoding="utf-8")
        tree, syntax_errors = parse_python_ast(
            source_code, relative_path, "TRACE_TEST_SYNTAX"
        )
        if syntax_errors or tree is None:
            continue
        for node in ast.walk(tree):
            entries.extend(_extract_function_trace_links(node, relative_path))
    return entries


def _referenced_artifact_ids(document: ArtifactDocument) -> set[str]:
    """Return all artifact IDs referenced by document frontmatter fields."""
    frontmatter = document.frontmatter
    references: set[str] = set()
    for key in (
        "traces_to",
        "depends_on",
        "target_artifacts",
        "affected_artifacts",
        "applies_to",
        "decisions",
    ):
        values = frontmatter.get(key, [])
        if isinstance(values, list):
            references.update(str(item) for item in values)
    for scalar in ("task_or_stage", "resolves", "resolved_by"):
        value = str(frontmatter.get(scalar, "")).strip()
        if value:
            references.add(value)
    return references


def _expand_intent_subgraph(
    intent_id: str, by_identifier: dict[str, ArtifactDocument]
) -> set[str]:
    """Return intent_id plus all non-Intent artifact IDs transitively linked to it."""
    subgraph_ids = {intent_id}
    for _ in range(5):
        for artifact_id, document in by_identifier.items():
            if document.artifact_type != "INT" and (
                _referenced_artifact_ids(document) & subgraph_ids
            ):
                subgraph_ids.add(artifact_id)
    return subgraph_ids


def group_artifacts_by_intent(
    by_identifier: dict[str, ArtifactDocument],
) -> list[tuple[str, dict[str, ArtifactDocument]]]:
    """Partition repository artifacts into per-Intent subgraphs and unlinked items."""
    intent_ids = sorted(
        aid for aid, doc in by_identifier.items() if doc.artifact_type == "INT"
    )
    claimed: set[str] = set()
    groups: list[tuple[str, dict[str, ArtifactDocument]]] = []
    for intent_id in intent_ids:
        subgraph_ids = _expand_intent_subgraph(intent_id, by_identifier)
        claimed.update(subgraph_ids)
        docs = {aid: by_identifier[aid] for aid in sorted(subgraph_ids)}
        groups.append((intent_id, docs))
    unlinked = {
        aid: doc for aid, doc in sorted(by_identifier.items()) if aid not in claimed
    }
    if unlinked:
        groups.append(("Unlinked Artifacts", unlinked))
    return groups


def _document_matches_target(document: ArtifactDocument, target: str) -> bool:
    """Return True if document matches target ID, path, references, or target_files."""
    frontmatter = document.frontmatter
    if str(frontmatter.get("id", "")) == target or document.path == target:
        return True
    supersedes = {str(item) for item in frontmatter.get("supersedes", [])}
    if target in (_referenced_artifact_ids(document) | supersedes):
        return True
    writes = frontmatter.get("write_files", [])
    if isinstance(writes, list) and target in {str(item) for item in writes}:
        return True
    target_files = frontmatter.get("target_files")
    if isinstance(target_files, dict):
        all_target_files = [
            str(item)
            for item in target_files.get("tests", [])
            + target_files.get("implementation", [])
        ]
        if target in all_target_files:
            return True
    return False


def _expand_matched_ids(
    by_identifier: dict[str, ArtifactDocument], target: str
) -> set[str]:
    """Find all artifact IDs directly or transitively connected to target."""
    matched_ids = {
        artifact_id
        for artifact_id, document in by_identifier.items()
        if _document_matches_target(document, target)
    }
    for _ in range(2):
        for artifact_id, document in by_identifier.items():
            if any(
                _document_matches_target(document, matched_id)
                or _document_matches_target(by_identifier[matched_id], artifact_id)
                for matched_id in list(matched_ids)
            ):
                matched_ids.add(artifact_id)
    return matched_ids


def _collect_matching_commit_lines(
    repository_root: Path, target_ids: set[str]
) -> list[str]:
    """Return formatted COMMIT lines for git log entries referencing target_ids."""
    lines: list[str] = []
    for commit_hash, subject in get_git_commit_subjects(repository_root):
        referenced_ids = set(COMMIT_ID_REGEX.findall(subject))
        if referenced_ids & target_ids:
            lines.append(f"COMMIT {commit_hash} -> {subject}")
    return lines


def trace_lineage(repository_root: Path, target: str) -> list[str]:
    """Return formatted bidirectional lineage lines for an artifact ID or filepath."""
    by_identifier = load_artifacts_by_id(repository_root)
    matched_ids = _expand_matched_ids(by_identifier, target)
    lines: list[str] = []
    for artifact_id in sorted(matched_ids):
        frontmatter = by_identifier[artifact_id].frontmatter
        status = frontmatter.get("status", frontmatter.get("verdict", "ok"))
        lines.append(f"{artifact_id} [{status}] ({by_identifier[artifact_id].path})")
    for (
        requirement_id,
        criterion_id,
        specification_id,
        location,
    ) in collect_test_trace_links(repository_root):
        matches = {
            requirement_id,
            specification_id,
            f"{requirement_id}:{criterion_id}",
            location.split(":")[0],
        }
        if (
            target in matches
            or requirement_id in matched_ids
            or specification_id in matched_ids
        ):
            pair = f"{requirement_id}:{criterion_id}, {specification_id}"
            lines.append(f"TEST {location} -> {pair}")
    lines.extend(
        _collect_matching_commit_lines(repository_root, {target, *matched_ids})
    )
    return lines


def _statement_lines_for_file(python_path: Path, repository_root: Path) -> set[int]:
    """Return executable AST statement line numbers for a Python source file."""
    relative_path = python_path.relative_to(repository_root).as_posix()
    tree, errors = parse_python_ast(
        python_path.read_text(encoding="utf-8"), relative_path, "TRACE_SRC_SYNTAX"
    )
    if errors or tree is None:
        return set()
    return {
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.stmt)
        and not (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        )
    }


def _run_sys_monitoring_pytest(
    repository_root: Path,
) -> tuple[int, dict[str, set[int]]]:
    """Run pytest under sys.monitoring in a clean subprocess and return hit lines."""
    report_dir = repository_root / ".report"
    report_dir.mkdir(parents=True, exist_ok=True)
    raw_file = report_dir / "raw_coverage.json"
    env = {
        **os.environ,
        "PYTHONPATH": str((repository_root / "src").resolve()),
        "MT_COVERAGE_ACTIVE": "1",
    }
    env.pop("PYTEST_CURRENT_TEST", None)
    subprocess.run(
        [sys.executable, "-c", _COVERAGE_RUNNER_SCRIPT],
        cwd=repository_root,
        env=env,
        capture_output=True,
        check=False,
    )
    if not raw_file.is_file():
        return 1, {}
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    raw_file.unlink(missing_ok=True)
    hit_map = {
        str(Path(path).resolve()): {int(line) for line in lines}
        for path, lines in payload.get("hit", {}).items()
    }
    return int(payload.get("exit_code", 1)), hit_map


def collect_pytest_line_coverage(repository_root: Path) -> dict[str, Any]:
    """Collect per-module line coverage via stdlib sys.monitoring and write JSON."""
    source_dir = repository_root / "src"
    exit_code, hit_map = _run_sys_monitoring_pytest(repository_root)
    modules: list[dict[str, Any]] = []
    total_covered = 0
    total_statements = 0
    for py_path in sorted(source_dir.rglob("*.py")) if source_dir.is_dir() else []:
        stmts = _statement_lines_for_file(py_path, repository_root)
        covered = len(stmts & hit_map.get(str(py_path.resolve()), set()))
        total = len(stmts)
        total_covered += covered
        total_statements += total
        pct = round((covered / total * 100.0), 1) if total else 100.0
        modules.append(
            {
                "module": py_path.relative_to(repository_root).as_posix(),
                "covered": covered,
                "statements": total,
                "percent": pct,
            }
        )
    overall = (
        round((total_covered / total_statements * 100.0), 1)
        if total_statements
        else 100.0
    )
    result: dict[str, Any] = {
        "exit_code": exit_code,
        "covered_lines": total_covered,
        "statement_lines": total_statements,
        "percent": overall,
        "modules": modules,
    }
    report_dir = repository_root / ".report"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "coverage.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result


def _compute_static_test_metrics(
    repository_root: Path,
) -> tuple[int, int, int, str]:
    """Return (test_files, test_functions, trace_links, ac_coverage_summary)."""
    test_dir = repository_root / "tests"
    test_files = len(list(test_dir.rglob("test_*.py"))) if test_dir.is_dir() else 0
    links = collect_test_trace_links(repository_root)
    unique_funcs = len({location for _, _, _, location in links})
    covered_pairs = {(req_id, ac_id) for req_id, ac_id, _, _ in links}
    total_criteria = {
        (aid, str(item.get("id", "")))
        for aid, doc in load_artifacts_by_id(repository_root).items()
        if doc.artifact_type == "REQ" and doc.frontmatter.get("status") != "deprecated"
        for item in doc.frontmatter.get("acceptance_criteria", [])
        if isinstance(item, dict) and item.get("id")
    }
    covered_ac = len(total_criteria & covered_pairs)
    total_ac = len(total_criteria)
    pct = (covered_ac / total_ac * 100.0) if total_ac else 100.0
    return test_files, unique_funcs, len(links), f"{covered_ac}/{total_ac} ({pct:.1f}%)"


def render_test_and_coverage_section(repository_root: Path) -> list[str]:
    """Render Section 8 static test/AC metrics and cached line coverage table."""
    files_cnt, funcs_cnt, links_cnt, ac_summary = _compute_static_test_metrics(
        repository_root
    )
    lines = [
        "## 8. Test & Code Coverage Report",
        "",
        "| Metric | Value |",
        "| :--- | :--- |",
        f"| Test Files | `{files_cnt}` |",
        f"| Traced Test Functions | `{funcs_cnt}` |",
        f"| `@traces` Bindings | `{links_cnt}` |",
        f"| AcceptanceCriteria Covered | `{ac_summary}` |",
    ]
    coverage_file = repository_root / ".report" / "coverage.json"
    if (
        not coverage_file.is_file()
        and "documentation" in sys.argv
        and not os.environ.get("PYTEST_CURRENT_TEST")
        and not os.environ.get("MT_COVERAGE_ACTIVE")
        and (repository_root / "src").is_dir()
        and (repository_root / "tests").is_dir()
    ):
        collect_pytest_line_coverage(repository_root)
    if coverage_file.is_file():
        cov = json.loads(coverage_file.read_text(encoding="utf-8"))
        cov_summary = (
            f"{cov.get('covered_lines', 0)}/{cov.get('statement_lines', 0)} "
            f"({cov.get('percent', 0.0):.1f}%)"
        )
        lines.extend(
            [
                f"| Pytest Exit Code | `{cov.get('exit_code', 0)}` |",
                f"| Total Line Coverage | `{cov_summary}` |",
                "",
                "| Module | Covered Lines | Executable Lines | Coverage |",
                "| :--- | :--- | :--- | :--- |",
            ]
        )
        for mod in cov.get("modules", []):
            lines.append(
                f"| `{mod['module']}` | `{mod['covered']}` | "
                f"`{mod['statements']}` | `{mod['percent']:.1f}%` |"
            )
    lines.append("")
    return lines
