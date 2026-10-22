"""TestContracts for traceability_checker and Git commit traceability."""

from pathlib import Path
import subprocess

from multi_tasker.checkers.schemas_checker import check_schemas
from multi_tasker.checkers.traceability_checker import check_traceability
from multi_tasker.cli.main import main
from multi_tasker.domain.models import traces
from multi_tasker.orchestrator.worktree import commit_traceable_change


def _write_document(path: Path, content: str) -> None:
    """Create parent directories and write file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_trace_fixtures(tmp_path: Path) -> None:
    """Create synthetic artifacts and test files for trace failure testing."""
    _write_document(
        tmp_path / "policy/artifact_schemas.yaml",
        "schemas: {REQ: {path_glob: 'artifacts/requirements/REQ-*.md'}}\n",
    )
    _write_document(tmp_path / "policy/traceability.yaml", "traceability_rules: {}\n")
    documents = {
        "artifacts/wrong_folder/REQ-099.md": "---\nid: REQ-099\nstatus: draft\n---\n",
        "artifacts/requirements/REQ-001.md": (
            "---\nid: REQ-001\nstatus: draft\ntraces_to: [INT-404]\n---\n"
        ),
        "artifacts/requirements/REQ-002.md": (
            "---\nid: REQ-002\nstatus: approved\n"
            "acceptance_criteria: [{id: AC-01}, {id: AC-02}]\n---\n"
        ),
        "artifacts/specifications/SPEC-001.md": (
            "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n"
            "covers_criteria: [REQ-002:AC-01]\n"
            "target_files: {tests: [tests/test_sample.py], "
            "implementation: [src/unplanned.py]}\n---\n"
        ),
        "artifacts/tasks/TASK-001.md": (
            "---\nid: TASK-001\nstatus: planned\ndepends_on: [TASK-002]\n"
            "write_files: [tests/test_sample.py]\n---\n"
        ),
        "artifacts/tasks/TASK-002.md": (
            "---\nid: TASK-002\ntype: implementation\nstatus: planned\n"
            "depends_on: [TASK-001]\nrequired_files: []\nwrite_files: []\n---\n"
        ),
        "src/undeclared.py": "val = 1\n",
        "tests/test_sample.py": (
            "from multi_tasker.domain.models import traces\n"
            "def test_untagged() -> None:\n    return None\n"
            '@traces("REQ-999", "AC-01", "SPEC-999")\n'
            "def test_bad_tag() -> None:\n    return None\n"
        ),
    }
    for relative_path, content in documents.items():
        _write_document(tmp_path / relative_path, content)


@traces("REQ-001", "AC-04", "SPEC-001")
def test_traceability_checker_all_failure_modes(tmp_path: Path) -> None:
    """Verify upstream approval, test contract coverage, and task cycle detection."""
    assert check_traceability(tmp_path)[0].rule_id == "TRACE_POLICY_MISSING"
    _seed_trace_fixtures(tmp_path)
    rules = {
        finding.rule_id
        for finding in [*check_schemas(tmp_path), *check_traceability(tmp_path)]
    }
    assert {
        "TRACE_PATH_GLOB_MISMATCH",
        "TRACE_MISSING_REF",
        "TRACE_UPSTREAM_NOT_APPROVED",
        "TRACE_UNCOVERED_REQ_AC",
        "TRACE_UNTAGGED_TEST",
        "TRACE_INVALID_TAG",
        "TRACE_MISSING_TEST_CONTRACT",
        "TRACE_TASK_CYCLE",
        "TRACE_IMPL_MISSING_TEST_DEP",
        "ARCH_UNDECLARED_TARGET_FILE",
        "TRACE_UNPLANNED_TARGET_FILE",
    }.issubset(rules)
    requirement_stage = {
        finding.rule_id
        for finding in check_traceability(
            tmp_path, ["artifacts/requirements/REQ-002.md"]
        )
    }
    assert "TRACE_UNCOVERED_REQ_AC" not in requirement_stage
    assert "TRACE_MISSING_TEST_CONTRACT" not in requirement_stage
    scoped_target_file = {
        finding.rule_id
        for finding in check_traceability(tmp_path, ["src/undeclared.py"])
    }
    assert "ARCH_UNDECLARED_TARGET_FILE" in scoped_target_file


@traces("REQ-001", "AC-04", "SPEC-001")
def test_git_commit_traceability_validation(tmp_path: Path) -> None:
    """Verify check_traceability validates Git commit format and referenced IDs."""
    _write_document(
        tmp_path / "policy/traceability.yaml",
        "traceability_rules: {verify_git_commit_traceability: true}\n",
    )
    intent_path = "artifacts/intents/INT-001.md"
    _write_document(tmp_path / intent_path, "---\nid: INT-001\nstatus: open\n---\n")
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    seed_cmd = ["git", "-c", "user.name=mt", "-c", "user.email=mt@local", "commit"]
    subprocess.run(
        [*seed_cmd, "-q", "-m", "INT-001: Seed intent [traces: INT-001]"],
        cwd=tmp_path,
        check=True,
    )
    assert check_traceability(tmp_path) == []
    _write_document(tmp_path / intent_path, "---\nid: INT-001\n---\n")
    commit_traceable_change(
        tmp_path, [intent_path], "INT-001: Bad ref [traces: REQ-999]"
    )
    assert "TRACE_COMMIT_UNKNOWN_ID" in {
        finding.rule_id for finding in check_traceability(tmp_path)
    }
    _write_document(
        tmp_path / intent_path, "---\nid: INT-001\nstatus: processed\n---\n"
    )
    commit_traceable_change(tmp_path, [intent_path], "unformatted")
    assert "TRACE_COMMIT_FORMAT" in {
        finding.rule_id for finding in check_traceability(tmp_path)
    }


@traces("REQ-004", "AC-03", "SPEC-004")
def test_git_commit_scope_and_intent_traceability(tmp_path: Path) -> None:
    """Verify check_traceability detects unscoped Task commits and orphan Intents."""
    _write_document(
        tmp_path / "policy/traceability.yaml",
        "traceability_rules: {verify_git_commit_traceability: true}\n",
    )
    _write_document(
        tmp_path / "artifacts/intents/INT-001.md",
        "---\nid: INT-001\nstatus: processed\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nstatus: done\nwrite_files: [src/allowed.py]\n---\n",
    )
    _write_document(tmp_path / "src/rogue.py", "VALUE = 1\n")
    assert main(["initialize", "--root", str(tmp_path)]) == 0
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    seed_cmd = ["git", "-c", "user.name=mt", "-c", "user.email=mt@local", "commit"]
    subprocess.run(
        [*seed_cmd, "-q", "-m", "TASK-001: Rogue write [traces: TASK-001]"],
        cwd=tmp_path,
        check=True,
    )
    rules = {finding.rule_id for finding in check_traceability(tmp_path)}
    assert {"TRACE_COMMIT_UNSCOPED_FILE", "TRACE_UNPROCESSED_INTENT"}.issubset(rules)


@traces("REQ-038", "AC-01", "SPEC-038")
@traces("REQ-038", "AC-02", "SPEC-038")
@traces("REQ-038", "AC-03", "SPEC-038")
def test_scoped_multi_req_and_spec_traceability_checks(tmp_path: Path) -> None:
    """Verify subgraph-scoped AC and target_files checks with sibling REQs/SPECs."""
    _write_document(tmp_path / "policy/traceability.yaml", "traceability_rules: {}\n")
    for req_id in ("REQ-001", "REQ-002"):
        _write_document(
            tmp_path / f"artifacts/requirements/{req_id}.md",
            f"---\nid: {req_id}\nstatus: approved\n"
            "acceptance_criteria: [{id: AC-01}, {id: AC-02}]\n---\n",
        )
    spec_1 = "artifacts/specifications/SPEC-001.md"
    _write_document(
        tmp_path / spec_1,
        "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01, REQ-001:AC-02]\n"
        "target_files: {tests: [tests/t1.py], implementation: [src/m1.py]}\n---\n",
    )
    assert check_traceability(tmp_path, [spec_1]) == []
    full_rules = {item.rule_id for item in check_traceability(tmp_path)}
    assert "TRACE_UNCOVERED_REQ_AC" in full_rules
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-002.md",
        "---\nid: SPEC-002\nstatus: approved\ntraces_to: [REQ-002]\n"
        "covers_criteria: [REQ-002:AC-01, REQ-002:AC-02]\n"
        "target_files: {tests: [tests/t2.py], implementation: [src/m2.py]}\n---\n",
    )
    task_1 = "artifacts/tasks/TASK-001.md"
    _write_document(
        tmp_path / task_1,
        "---\nid: TASK-001\ntype: test_contract\nstatus: ready\n"
        "traces_to: [REQ-001, SPEC-001]\ndepends_on: []\nrequired_files: []\n"
        "write_files: [tests/t1.py, src/m1.py]\n---\n",
    )
    assert check_traceability(tmp_path, [task_1]) == []
    assert "TRACE_UNPLANNED_TARGET_FILE" in {
        item.rule_id for item in check_traceability(tmp_path)
    }
    _write_document(
        tmp_path / spec_1,
        "---\nid: SPEC-001\nstatus: draft\ntraces_to: [REQ-001]\n"
        "covers_criteria: [REQ-001:AC-01]\n---\n",
    )
    bad_spec = {item.rule_id for item in check_traceability(tmp_path, [spec_1])}
    assert "TRACE_UNCOVERED_REQ_AC" in bad_spec
