"""TestContracts for schemas_checker, state transitions, and task budgets."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from multi_tasker.checkers import permissions_checker
from multi_tasker.checkers.schemas_checker import validate_schema_node
from multi_tasker.cli.main import main
from multi_tasker.domain import parser as domain_parser
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file, parse_artifact_file
from multi_tasker.orchestrator.prompt_builder import build_agent_prompt
from tests.test_lifecycle import REPOSITORY_ROOT, _write_document
from tests.test_orchestrator import _seed_minimal_policies


def _write_text(path: Path, text: str) -> None:
    """Create parent folders and write text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@traces("REQ-001", "AC-04", "SPEC-001")
@pytest.mark.parametrize(
    ("value", "schema", "expected_rule"),
    [
        ("not-int", {"type": "integer"}, "TRACE_SCHEMA_TYPE"),
        (True, {"type": "integer"}, "TRACE_SCHEMA_TYPE"),
        (123, {"type": ["string", "null"]}, "TRACE_SCHEMA_TYPE"),
        ("bad", {"type": "string", "enum": ["ok"]}, "TRACE_SCHEMA_ENUM"),
        (0, {"type": "integer", "minimum": 1}, "TRACE_SCHEMA_MIN"),
        ("abc", {"type": "string", "pattern": "^REQ-"}, "TRACE_SCHEMA_PATTERN"),
        ("ab", {"type": "string", "minLength": 5}, "TRACE_SCHEMA_MIN_LEN"),
        ("abcdef", {"type": "string", "maxLength": 3}, "TRACE_SCHEMA_MAX_LEN"),
        ([], {"type": "array", "minItems": 1}, "TRACE_SCHEMA_MIN_ITEMS"),
        ([1, 2], {"type": "array", "maxItems": 1}, "TRACE_SCHEMA_MAX_ITEMS"),
        ({}, {"type": "object", "required": ["id"]}, "TRACE_SCHEMA_REQUIRED"),
        (
            {"id": "1", "extra": 2},
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {"id": {"type": "string"}},
            },
            "TRACE_SCHEMA_UNKNOWN_FIELD",
        ),
    ],
)
def test_schemas_checker_branches(
    value: Any, schema: dict[str, Any], expected_rule: str
) -> None:
    """Verify every JSON-Schema validation rule in memory."""
    findings = validate_schema_node(value, schema, "artifact.md", "field")
    assert expected_rule in {finding.rule_id for finding in findings}
    assert validate_schema_node(None, {"type": ["string", "null"]}, "a.md") == []
    assert validate_schema_node(True, {"type": "boolean"}, "a.md") == []


@traces("REQ-019", "AC-01", "SPEC-019")
@traces("REQ-019", "AC-02", "SPEC-019")
@traces("REQ-045", "AC-01", "SPEC-045")
@traces("REQ-048", "AC-02", "SPEC-048")
def test_aligned_policy_limits_and_prompt_artifact_constraints() -> None:
    """Verify aligned policy limits and role prompt artifact constraint rendering."""
    repository_root = Path(__file__).resolve().parent.parent
    limits_cfg = load_yaml_file(repository_root / "policy/code_limits.yaml")[
        "source_code"
    ]
    assert limits_cfg["max_function_lines"] == 50
    assert limits_cfg["max_function_args"] == 6
    schemas_cfg = load_yaml_file(repository_root / "policy/artifact_schemas.yaml")
    artifacts_cfg = load_yaml_file(repository_root / "policy/artifact_limits.yaml")[
        "artifacts"
    ]
    assert artifacts_cfg["REQ"]["max_criterion_words"] == 45
    assert artifacts_cfg["TASK"]["max_write_files"] == 8
    assert artifacts_cfg["TASK"]["max_required_files"] == 10
    task_props = schemas_cfg["schemas"]["TASK"]["json_schema"]["properties"]
    assert task_props["write_files"]["maxItems"] == 8
    assert task_props["required_files"]["maxItems"] == 10
    req_prompt, req_errors = build_agent_prompt(repository_root, "requirement-agent")
    assert not req_errors
    assert "- **Artifact Limit `max_criterion_words`**: `45`" in req_prompt
    assert "- **Artifact Limit `max_acceptance_criteria`**: `5`" in req_prompt
    assert ", single paragraph only" in req_prompt
    plan_prompt, plan_errors = build_agent_prompt(repository_root, "planner-agent")
    assert not plan_errors
    assert "- **Artifact Limit `max_write_files`**: `8`" in plan_prompt
    assert "- **Artifact Limit `max_required_files`**: `10`" in plan_prompt


def _seed_colliding_tasks_and_spec(eval_root: Path) -> None:
    """Seed TASK-001, TASK-002, and approved SPEC-001 in eval_root."""
    _write_text(
        eval_root / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\ntitle: T1\ntype: test_contract\nstatus: planned\n"
        "traces_to: [REQ-001, SPEC-001]\ndepends_on: []\nrequired_files: []\n"
        "write_files: [tests/test_a.py]\nverification_cmd: pytest\n---\n"
        "## Objective\nO.\n\n## Scoped Instructions\nI.\n",
    )
    _write_text(
        eval_root / "artifacts/tasks/TASK-002.md",
        "---\nid: TASK-002\ntitle: T2\ntype: implementation\nstatus: planned\n"
        "traces_to: [REQ-001, SPEC-001]\ndepends_on: [TASK-001]\n"
        "required_files: [tests/test_a.py]\nwrite_files: [src/a.py]\n"
        "verification_cmd: pytest\n---\n"
        "## Objective\nO.\n\n## Scoped Instructions\nI.\n",
    )
    _write_text(
        eval_root / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\ntitle: Spec\nstatus: approved\n"
        "traces_to: [REQ-001]\ncovers_criteria: [REQ-001:AC-01]\ndecisions: []\n"
        "target_files: {tests: [tests/test_a.py], implementation: [src/a.py]}\n---\n",
    )


@traces("REQ-023", "AC-01", "SPEC-023")
@traces("REQ-023", "AC-02", "SPEC-023")
def test_programmatic_id_normalization_and_streamlined_pipeline_checks(
    tmp_path: Path,
) -> None:
    """Verify next_artifact_id, normalize_new_stage_artifacts, and deferred AC check."""
    from multi_tasker.checkers.code_and_git_traceability import (
        check_test_contract_coverage,
    )
    from multi_tasker.domain.parser import (
        load_artifacts_by_id,
        next_artifact_id,
        normalize_new_stage_artifacts,
    )
    from multi_tasker.orchestrator.lifecycle import bootstrap_evaluation_repository

    eval_root = tmp_path / "eval_repo"
    bootstrap_evaluation_repository(eval_root, "Add helper.")
    pipeline_cfg = load_yaml_file(eval_root / "policy/artifact_lifecycle.yaml")
    assert pipeline_cfg["stages"][2]["approval_gate"] == "auto"
    assert next_artifact_id(eval_root, "INT") == "INT-002"
    assert next_artifact_id(eval_root, "TASK") == "TASK-001"
    _seed_colliding_tasks_and_spec(eval_root)
    renamed = normalize_new_stage_artifacts(
        eval_root,
        {"TASK-001"},
        ["artifacts/tasks/TASK-001.md", "artifacts/tasks/TASK-002.md"],
    )
    assert renamed == ["artifacts/tasks/TASK-002.md", "artifacts/tasks/TASK-003.md"]
    doc_three, _ = parse_artifact_file(
        eval_root / "artifacts/tasks/TASK-003.md", "artifacts/tasks/TASK-003.md"
    )
    assert doc_three is not None and doc_three.frontmatter["id"] == "TASK-003"
    assert doc_three.frontmatter["depends_on"] == ["TASK-002"]
    by_id = load_artifacts_by_id(eval_root)
    assert check_test_contract_coverage(eval_root, by_id, {}) == []
    repository_root = Path(__file__).resolve().parent.parent
    plan_prompt, _ = build_agent_prompt(repository_root, "planner-agent")
    assert "Assigned Next Artifact ID" in plan_prompt
    assert "Planner Decomposition Contract" in plan_prompt


@traces("REQ-024", "AC-01", "SPEC-024")
def test_gitignore_scaffolding_and_changed_files_exclude_python_caches(
    tmp_path: Path,
) -> None:
    """Verify .gitignore and get_git_changed_files exclude Python cache files."""
    import subprocess
    from multi_tasker.checkers.common import get_git_changed_files
    from multi_tasker.orchestrator.lifecycle import bootstrap_evaluation_repository

    eval_root = tmp_path / "cache_repo"
    bootstrap_evaluation_repository(eval_root, "Verify cache ignore.")
    gitignore = (eval_root / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("__pycache__/", "*.py[cod]", ".pytest_cache/"):
        assert pattern in gitignore
    (eval_root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    subprocess.run(
        ["git", "commit", "-am", "INT-001: Trim gitignore [traces: INT-001]"],
        cwd=eval_root,
        capture_output=True,
        check=True,
    )
    _write_text(eval_root / "tests/__pycache__/test_x.cpython-312.pyc", "bytecode")
    _write_text(eval_root / ".pytest_cache/v/cache/nodeids", "[]")
    _write_text(eval_root / "tests/test_x.py", "def test_x() -> None:\n    pass\n")
    assert get_git_changed_files(eval_root) == ["tests/test_x.py"]


def _is_expected_valid_transition(
    rule: dict[str, object],
    state_map: dict[str, list[str]],
    old_state: str | None,
    new_state: str,
) -> bool:
    """Return True if rule and state_map permit old_state -> new_state."""
    allowed_existing = rule.get("allowed_existing_states")
    allowed_targets = rule.get("allowed_target_states")
    existing_ok = (
        rule.get("allow_create", True) is not False
        if old_state is None
        else (not isinstance(allowed_existing, list) or old_state in allowed_existing)
    )
    target_ok = not isinstance(allowed_targets, list) or new_state in allowed_targets
    step_ok = (
        old_state is None
        or old_state == new_state
        or not state_map
        or new_state in state_map.get(old_state, [])
    )
    return bool(existing_ok and target_ok and step_ok)


def _verify_rule_state_matrix(
    root: Path,
    role: str,
    rule: dict[str, object],
    transitions: dict[str, dict[str, list[str]]],
) -> int:
    """Test every (old_state, new_state) pair for one agent permission rule."""
    sample_path = str(rule["path"]).replace("*", "001")
    artifact_type = domain_parser.infer_artifact_type(sample_path)
    state_map = transitions.get(artifact_type, {})
    all_states = list(state_map.keys()) or ["pass"]
    checked = 0
    for old_state in [None, *all_states]:
        for new_state in all_states:
            _write_document(
                root / sample_path, f"---\nid: ART-001\nstatus: {new_state}\n---\n"
            )
            prior = {sample_path: old_state} if old_state is not None else {}
            findings = permissions_checker.check_permissions(
                root, role, None, [sample_path], prior
            )
            expected = _is_expected_valid_transition(
                rule, state_map, old_state, new_state
            )
            assert (findings == []) == expected
            checked += 1
    return checked


@traces("REQ-007", "AC-01", "SPEC-007")
def test_approve_specification_and_dirty_task_propagation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify mt approve transitions SPEC from draft/in_review and dirties Tasks."""
    _seed_minimal_policies(tmp_path)
    real_lifecycle = load_yaml_file(REPOSITORY_ROOT / "policy/artifact_lifecycle.yaml")
    _write_document(
        tmp_path / "policy/artifact_lifecycle.yaml",
        yaml.safe_dump({"state_transitions": real_lifecycle["state_transitions"]}),
    )
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\nstatus: draft\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nstatus: done\ntraces_to: [SPEC-001]\n---\n",
    )
    assert main(["approve", "SPEC-001", "--root", str(tmp_path)]) == 0
    spec_doc, _ = domain_parser.parse_artifact_file(
        tmp_path / "artifacts/specifications/SPEC-001.md", "SPEC-001.md"
    )
    task_doc, _ = domain_parser.parse_artifact_file(
        tmp_path / "artifacts/tasks/TASK-001.md", "TASK-001.md"
    )
    assert spec_doc and spec_doc.frontmatter["status"] == "approved"
    assert task_doc and task_doc.frontmatter["status"] == "needs_update"
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-002.md",
        "---\nid: SPEC-002\nstatus: blocked\n---\n",
    )
    assert main(["approve", "SPEC-002", "--root", str(tmp_path)]) == 1
    assert "[PERM_INVALID_STATE_TRANSITION]" in capsys.readouterr().out


@traces("REQ-007", "AC-02", "SPEC-007")
def test_exhaustive_agent_and_lifecycle_state_transitions(tmp_path: Path) -> None:
    """Verify every (agent_role, existing_state, target_state) and CLI approval."""
    _seed_minimal_policies(tmp_path)
    real_permissions = load_yaml_file(REPOSITORY_ROOT / "policy/agent_permissions.yaml")
    real_lifecycle = load_yaml_file(REPOSITORY_ROOT / "policy/artifact_lifecycle.yaml")
    transitions = real_lifecycle["state_transitions"]
    _write_document(
        tmp_path / "policy/agent_permissions.yaml", yaml.safe_dump(real_permissions)
    )
    _write_document(
        tmp_path / "policy/artifact_lifecycle.yaml",
        yaml.safe_dump({"state_transitions": transitions}),
    )
    total_checked = 0
    for role, config in real_permissions["agents"].items():
        for rule in [
            *config.get("allowed_write", []),
            *config.get("escalation_write", []),
        ]:
            if rule["path"] != "$TASK_WRITE_FILES":
                total_checked += _verify_rule_state_matrix(
                    tmp_path, role, rule, transitions
                )
    assert total_checked >= 150
    for folder, prefix in (
        ("requirements", "REQ"),
        ("specifications", "SPEC"),
        ("decisions", "DEC"),
    ):
        for state, allowed_next in transitions[prefix].items():
            artifact_id = f"{prefix}-099"
            _write_document(
                tmp_path / "artifacts" / folder / f"{artifact_id}.md",
                f"---\nid: {artifact_id}\nstatus: {state}\n---\n",
            )
            exit_code = main(["approve", artifact_id, "--root", str(tmp_path)])
            assert (exit_code == 0) == ("approved" in allowed_next)
