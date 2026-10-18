"""Parametrized TestContracts for permissions, glossary, schemas, and limits."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from src.checkers.glossary_checker import check_glossary
from src.checkers.limits_checker import check_limits
from src.checkers.permissions_checker import check_permissions
from src.checkers.schemas_checker import check_schemas
from src.domain.models import traces
from src.domain.parser import infer_artifact_type, load_yaml_file, parse_artifact_file
from src.orchestrator.prompt_builder import build_agent_prompt

SYNTHETIC_PERMISSIONS: dict[str, Any] = {
    "global_forbidden_write": ["policy/**"],
    "agents": {
        "req-agent": {
            "allowed_write": [
                {
                    "path": "artifacts/requirements/REQ-*.md",
                    "allowed_existing_states": ["draft"],
                }
            ],
            "escalation_write": [{"path": "artifacts/escalations/ESC-*.md"}],
        },
        "rev-agent": {
            "allowed_write": [
                {"path": "artifacts/reviews/REV-*.md", "allow_create": False}
            ],
            "escalation_write": [],
        },
        "worker-agent": {
            "allowed_write": [
                {
                    "path": "$TASK_WRITE_FILES",
                    "require_task_state": "in_progress",
                    "task_type_path_constraints": {"implementation": ["src/**"]},
                }
            ],
            "escalation_write": [{"path": "artifacts/escalations/ESC-*.md"}],
        },
    },
}

SYNTHETIC_LIMITS: dict[str, Any] = {
    "artifacts": {
        "REQ": {
            "max_body_words": 2,
            "max_acceptance_criteria": 1,
            "max_criterion_words": 1,
            "required_sections": ["Statement", "MissingSec"],
            "sections": {
                "Statement": {
                    "max_words": 2,
                    "max_lines": 1,
                    "single_paragraph_only": True,
                }
            },
        },
        "TASK": {"max_write_files": 1, "max_required_files": 1},
        "REV": {"max_findings_per_record": 1, "max_finding_words": 1},
    },
    "source_code": {
        "max_file_lines": 4,
        "max_function_lines": 2,
        "max_function_args": 1,
        "max_class_methods": 1,
        "max_docstring_lines": 1,
        "max_docstring_words": 2,
        "max_inline_comment_lines": 1,
        "max_inline_comment_words": 2,
    },
}


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a synthetic policy dictionary as YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    """Create parent folders and write text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@traces("REQ-001", "AC-01", "SPEC-001")
@pytest.mark.parametrize(
    ("role", "changed", "states", "expected_rule"),
    [
        (None, ["policy/limits.yaml"], {}, "PERM_POLICY_MODIFIED"),
        ("unknown-role", ["src/mod.py"], {}, "PERM_UNKNOWN_AGENT"),
        ("req-agent", ["policy/limits.yaml"], {}, "PERM_FORBIDDEN_PATH"),
        ("req-agent", ["src/mod.py"], {}, "PERM_OUTSIDE_WRITE_SCOPE"),
        ("rev-agent", ["artifacts/reviews/REV-001.md"], {}, "PERM_CREATE_FORBIDDEN"),
        (
            "req-agent",
            ["artifacts/requirements/REQ-001.md"],
            {"artifacts/requirements/REQ-001.md": "approved"},
            "PERM_INVALID_STATE_EDIT",
        ),
        ("rev-agent", ["artifacts/escalations/ESC-001.md"], {}, "PERM_ESC_NOT_ALLOWED"),
        (
            "req-agent",
            ["artifacts/escalations/ESC-001.md", "artifacts/escalations/ESC-002.md"],
            {},
            "PERM_ESC_MULTIPLE",
        ),
        (
            "req-agent",
            ["artifacts/escalations/ESC-001.md", "artifacts/requirements/REQ-001.md"],
            {},
            "PERM_ESC_EXCLUSIVITY",
        ),
    ],
)
def test_permissions_checker_matrix(
    tmp_path: Path,
    role: str | None,
    changed: list[str],
    states: dict[str, str],
    expected_rule: str,
) -> None:
    """Verify permission rejection rules across synthetic scenarios."""
    assert check_permissions(tmp_path)[0].rule_id == "PERM_POLICY_MISSING"
    _write_yaml(tmp_path / "policy" / "permissions.yaml", SYNTHETIC_PERMISSIONS)
    findings = check_permissions(tmp_path, role, None, changed, states)
    assert expected_rule in {finding.rule_id for finding in findings}


@traces("REQ-001", "AC-01", "SPEC-001")
def test_permissions_worker_task_write_scope(tmp_path: Path) -> None:
    """Verify worker-agent $TASK_WRITE_FILES state and path constraints."""
    _write_yaml(tmp_path / "policy" / "permissions.yaml", SYNTHETIC_PERMISSIONS)
    missing_id = check_permissions(tmp_path, "worker-agent", None, ["src/app.py"])
    assert any(finding.rule_id == "PERM_TASK_ID_MISSING" for finding in missing_id)
    missing_task = check_permissions(
        tmp_path, "worker-agent", "TASK-404", ["src/app.py"]
    )
    assert any(finding.rule_id == "PERM_TASK_NOT_FOUND" for finding in missing_task)
    _write_text(
        tmp_path / "artifacts" / "tasks" / "TASK-010.md",
        "---\nid: TASK-010\ntype: implementation\nstatus: planned\n"
        "write_files: [tests/test_x.py, src/app.py]\n---\n",
    )
    findings = check_permissions(tmp_path, "worker-agent", "TASK-010", ["src/app.py"])
    rules = {finding.rule_id for finding in findings}
    assert {"PERM_TASK_STATE", "PERM_LOCKED_TEST_CONTRACT"}.issubset(rules)


@traces("REQ-001", "AC-02", "SPEC-001")
def test_parser_and_glossary_branches(tmp_path: Path) -> None:
    """Verify parser edge cases and glossary prose/AST identifier checks."""
    assert check_glossary(tmp_path)[0].rule_id == "GLOSSARY_POLICY_MISSING"
    _write_text(tmp_path / "list.yaml", "- item1\n")
    assert load_yaml_file(tmp_path / "list.yaml") == {}
    assert infer_artifact_type("REQ-001.md") == "REQ"
    _write_text(tmp_path / "no_frontmatter.md", "just text\n")
    _write_text(tmp_path / "not_mapping.md", "---\n- a\n---\n")
    _, error_one = parse_artifact_file(tmp_path / "no_frontmatter.md", "a.md")
    _, error_two = parse_artifact_file(tmp_path / "not_mapping.md", "b.md")
    assert error_one[0].rule_id == "TRACE_FRONTMATTER_MISSING"
    assert error_two[0].rule_id == "TRACE_YAML_NOT_MAP"
    bad_synonym, synonym_beta = "Legacy" + "Term", "J" + "ob"
    glossary = {
        "enforcement": {"check_markdown_prose": True, "check_file_names": True},
        "terms": [
            {"canonical": "Intent", "forbidden_synonyms": [bad_synonym, synonym_beta]}
        ],
    }
    _write_yaml(tmp_path / "policy/glossary.yaml", glossary)
    _write_text(
        tmp_path / "artifacts/requirements/REQ-001.md",
        f"```text\n{bad_synonym}\n```\nProse {bad_synonym} in src/mod.py.\n",
    )
    _write_text(
        tmp_path / "src" / f"{synonym_beta.lower()}_mod.py",
        "class intent:\n    command_history = 1\n"
        f"def run_{bad_synonym.lower()}({synonym_beta.lower()}_id: int) -> None:\n"
        "    pass\n",
    )
    findings = check_glossary(tmp_path)
    expected = {
        "GLOSSARY_FORBIDDEN",
        "GLOSSARY_FORBIDDEN_FILE",
        "GLOSSARY_FORBIDDEN_IDENT",
        "GLOSSARY_CASE_MISMATCH",
    }
    assert {finding.rule_id for finding in findings} == expected
    assert all("command_history" not in finding.message for finding in findings)


@traces("REQ-001", "AC-02", "SPEC-001")
def test_limits_checker_artifact_and_code_branches(tmp_path: Path) -> None:
    """Verify synthetic artifact section/count limits and Python AST/comment limits."""
    assert check_schemas(tmp_path)[0].rule_id == "SCHEMA_POLICY_MISSING"
    assert check_limits(tmp_path)[0].rule_id == "LIMIT_POLICY_MISSING"
    _write_yaml(tmp_path / "policy/schemas.yaml", SYNTHETIC_LIMITS)
    _write_yaml(tmp_path / "policy/limits.yaml", SYNTHETIC_LIMITS)
    _write_text(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\n"
        "acceptance_criteria: [{id: AC-01, criterion: two words}, {id: AC-02}]\n---\n"
        "## Statement\none two three\n\npara two\n",
    )
    _write_text(
        tmp_path / "artifacts/tasks/TASK-001.md",
        "---\nid: TASK-001\nwrite_files: [a, b]\nrequired_files: [c, d]\n---\n",
    )
    _write_text(
        tmp_path / "artifacts/reviews/REV-001.md",
        "---\nid: REV-001\nfindings: [two words, second]\n---\n",
    )
    _write_text(
        tmp_path / "src/over.py",
        '"""One two three\nline two."""\n# c1 w2 w3\n# c2\n'
        "class Box:\n    def m1(self, alpha: int, beta: int) -> int:\n"
        "        result = 1\n        return result\n"
        "    def m2(self) -> int:\n        return 2\n",
    )
    rules = {
        finding.rule_id
        for finding in [*check_schemas(tmp_path), *check_limits(tmp_path)]
    }
    assert len(rules) >= 19 and "LIMIT_COMMENT_WORDS" in rules


@traces("REQ-001", "AC-01", "SPEC-001")
@traces("REQ-001", "AC-02", "SPEC-001")
def test_real_policy_permissions_glossary_limits_sensitivity(tmp_path: Path) -> None:
    """Verify real policy configs and toggle sensitivity for permissions and schemas."""
    repository_root = Path(__file__).resolve().parent.parent
    real_permissions = load_yaml_file(repository_root / "policy/permissions.yaml")
    _write_yaml(tmp_path / "policy/permissions.yaml", real_permissions)
    escalation = "artifacts/escalations/ESC-001.md"
    escalation_edit = check_permissions(
        tmp_path, "requirement-agent", None, [escalation], {escalation: "open"}
    )
    assert escalation_edit[0].rule_id == "PERM_INVALID_STATE_EDIT"
    real_permissions["agents"]["requirement-agent"]["read_scope"] = ["artifacts/**"]
    real_permissions["escalation_exclusivity"][
        "forbid_domain_writes_when_escalating"
    ] = False
    _write_yaml(tmp_path / "policy/permissions.yaml", real_permissions)
    scope_outside = check_permissions(tmp_path, "requirement-agent", None, ["src/a.py"])
    assert scope_outside[0].rule_id == "PERM_OUTSIDE_READ_SCOPE"
    escalation_both = check_permissions(
        tmp_path,
        "requirement-agent",
        None,
        [escalation, "artifacts/requirements/REQ-001.md"],
    )
    assert all(finding.rule_id != "PERM_ESC_EXCLUSIVITY" for finding in escalation_both)
    real_schemas = load_yaml_file(repository_root / "policy/schemas.yaml")
    _write_yaml(tmp_path / "policy/schemas.yaml", real_schemas)
    requirement_file = repository_root / "artifacts/requirements/REQ-001.md"
    _write_text(
        tmp_path / "artifacts/requirements/REQ-001.md",
        requirement_file.read_text("utf-8"),
    )
    assert check_schemas(tmp_path) == []
    real_schemas["artifacts"]["REQ"]["max_criterion_words"] = 5
    _write_yaml(tmp_path / "policy/schemas.yaml", real_schemas)
    assert check_schemas(tmp_path)[0].rule_id == "LIMIT_CRITERION_WORDS"


@traces("REQ-019", "AC-01", "SPEC-019")
@traces("REQ-019", "AC-02", "SPEC-019")
def test_aligned_policy_limits_and_prompt_artifact_constraints() -> None:
    """Verify aligned policy limits and role prompt artifact constraint rendering."""
    repository_root = Path(__file__).resolve().parent.parent
    limits_cfg = load_yaml_file(repository_root / "policy/limits.yaml")["source_code"]
    assert limits_cfg["max_function_lines"] == 50
    assert limits_cfg["max_function_args"] == 6
    schemas_cfg = load_yaml_file(repository_root / "policy/schemas.yaml")
    artifacts_cfg = schemas_cfg["artifacts"]
    assert artifacts_cfg["REQ"]["max_criterion_words"] == 45
    assert artifacts_cfg["TASK"]["max_write_files"] == 4
    assert artifacts_cfg["TASK"]["max_required_files"] == 6
    task_props = schemas_cfg["schemas"]["TASK"]["json_schema"]["properties"]
    assert task_props["write_files"]["maxItems"] == 4
    assert task_props["required_files"]["maxItems"] == 6
    req_prompt, req_errors = build_agent_prompt(repository_root, "requirement-agent")
    assert not req_errors
    assert "- **Artifact Limit `max_criterion_words`**: `45`" in req_prompt
    assert "- **Artifact Limit `max_acceptance_criteria`**: `5`" in req_prompt
    assert ", single paragraph only" in req_prompt
    plan_prompt, plan_errors = build_agent_prompt(repository_root, "planner-agent")
    assert not plan_errors
    assert "- **Artifact Limit `max_write_files`**: `4`" in plan_prompt
    assert "- **Artifact Limit `max_required_files`**: `6`" in plan_prompt
