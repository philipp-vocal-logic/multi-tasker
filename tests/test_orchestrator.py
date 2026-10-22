"""Parametrized TestContracts for Worktree, MergeGate, Scheduler, and Router."""

import os
from pathlib import Path
import shutil

import pytest
import yaml

from multi_tasker.checkers import (
    architecture_checker,
    clean_code_checker,
    common,
    glossary_checker,
    limits_checker,
    permissions_checker,
    schemas_checker,
    traceability_checker,
)
from multi_tasker.cli import output as cli_output
from multi_tasker.cli.main import main
from multi_tasker.domain import parser as domain_parser
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file
from multi_tasker.orchestrator import worktree
from multi_tasker.orchestrator.merge_gate import GateRequest, evaluate_merge_gate
from multi_tasker.orchestrator.router import route_escalation
from multi_tasker.orchestrator.scheduler import (
    compute_dirty_subgraph,
    select_parallel_batch,
)
from multi_tasker.orchestrator.worktree import (
    compute_policy_sha256,
    create_worktree,
    remove_worktree,
    verify_clean_repository,
)

POLICY_CONSUMING_MODULES = (
    architecture_checker,
    clean_code_checker,
    glossary_checker,
    limits_checker,
    permissions_checker,
    schemas_checker,
    traceability_checker,
    cli_output,
    domain_parser,
    worktree,
)


def _write_document(path: Path, text: str) -> None:
    """Create parent folders and write text file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_minimal_policies(root: Path) -> None:
    """Write minimal synthetic policy/*.yaml files into root."""
    requirement_rule = {
        "path": "artifacts/requirements/REQ-*.md",
        "allowed_existing_states": ["draft", "needs_update"],
        "allowed_target_states": ["draft", "in_review"],
    }
    agent_rules = {
        "allowed_write": [requirement_rule],
        "escalation_write": [{"path": "artifacts/escalations/ESC-*.md"}],
    }
    permissions = {
        "global_forbidden_write": ["policy/**"],
        "agents": {"req-agent": agent_rules},
    }
    transitions = {"REQ": {"draft": ["in_review"], "needs_update": ["draft"]}}
    for name, data in {
        "agent_permissions.yaml": permissions,
        "agent_execution.yaml": {"clean_repo_invariants": {}},
        "glossary.yaml": {"enforcement": {}, "terms": []},
        "code_limits.yaml": {"source_code": {}},
        "code_quality.yaml": {"linters": {"ruff": {"enabled": False}}, "ast_rules": {}},
        "code_architecture.yaml": {"dependency_rules": {}, "layers": []},
        "artifact_schemas.yaml": {"schemas": {}},
        "artifact_limits.yaml": {"artifacts": {}},
        "artifact_lifecycle.yaml": {"state_transitions": transitions},
        "traceability.yaml": {"traceability_rules": {}},
    }.items():
        _write_document(root / "policy" / name, yaml.safe_dump(data))


@traces("REQ-002", "AC-01", "SPEC-002")
def test_worktree_lifecycle_and_clean_repo_checks(tmp_path: Path) -> None:
    """Verify policy SHA-256 digest, dirty-repo guard, and read-only Worktree."""
    assert len(compute_policy_sha256(tmp_path)) == 64
    assert verify_clean_repository(tmp_path) == []
    _seed_minimal_policies(tmp_path)
    base_hash = compute_policy_sha256(tmp_path)
    assert verify_clean_repository(tmp_path, expected_policy_sha256=base_hash) == []
    bad = verify_clean_repository(tmp_path, expected_policy_sha256="wrong-hash")
    assert any(finding.rule_id == "GATE_POLICY_TAMPERED" for finding in bad)
    worktree_path = create_worktree(tmp_path, "run-01")
    assert worktree_path.exists()
    assert not os.access(worktree_path / "policy/agent_permissions.yaml", os.W_OK)
    remove_worktree(tmp_path, worktree_path)
    remove_worktree(tmp_path, worktree_path)
    assert not worktree_path.exists()


@traces("REQ-002", "AC-02", "SPEC-002")
def test_merge_gate_enforces_tamper_perms_escalation_and_cmd(tmp_path: Path) -> None:
    """Verify MergeGate outcomes for empty diff, tamper, Escalation, and pass/fail."""
    base, worktree_dir, agent = tmp_path / "base", tmp_path / "wt", "req-agent"
    _seed_minimal_policies(base)
    _seed_minimal_policies(worktree_dir)
    empty = evaluate_merge_gate(GateRequest(base, worktree_dir, agent, None, None, []))
    assert empty.findings[0].rule_id == "GATE_EMPTY_DIFF"
    escalation_path = "artifacts/escalations/ESC-001.md"
    _write_document(worktree_dir / escalation_path, "---\nid: ESC-001\n---\n")
    assert evaluate_merge_gate(
        GateRequest(base, worktree_dir, agent, changed_files=[escalation_path])
    ).escalated
    requirement_path = "artifacts/requirements/REQ-001.md"
    _write_document(
        base / requirement_path, "---\nid: REQ-001\nstatus: needs_update\n---\n"
    )
    _write_document(
        worktree_dir / requirement_path, "---\nid: REQ-001\nstatus: in_review\n---\n"
    )
    bad = evaluate_merge_gate(
        GateRequest(base, worktree_dir, agent, changed_files=[requirement_path])
    )
    assert bad.findings[0].rule_id == "PERM_INVALID_STATE_TRANSITION"
    _write_document(
        worktree_dir / requirement_path, "---\nid: REQ-001\nstatus: draft\n---\n"
    )
    pass_cmd, fail_cmd = "python3 -c 'exit(0)'", "python3 -c 'exit(2)'"
    assert evaluate_merge_gate(
        GateRequest(base, worktree_dir, agent, None, pass_cmd, [requirement_path])
    ).passed
    failing = evaluate_merge_gate(
        GateRequest(base, worktree_dir, agent, None, fail_cmd, [requirement_path])
    )
    assert failing.findings[0].rule_id == "GATE_VERIFY_CMD_FAILED"
    _write_document(worktree_dir / "policy/extra.yaml", "tampered: true\n")
    tamper = evaluate_merge_gate(
        GateRequest(base, worktree_dir, agent, changed_files=[requirement_path])
    )
    assert tamper.findings[0].rule_id == "GATE_POLICY_TAMPERED"


@traces("REQ-004", "AC-01", "SPEC-004")
def test_merge_gate_enforces_verification_command_timeout(tmp_path: Path) -> None:
    """Verify MergeGate emits GATE_VERIFY_CMD_TIMEOUT when verification_cmd hangs."""
    base, worktree_dir, agent = tmp_path / "base", tmp_path / "wt", "req-agent"
    _seed_minimal_policies(base)
    _seed_minimal_policies(worktree_dir)
    requirement_path = "artifacts/requirements/REQ-001.md"
    _write_document(
        worktree_dir / requirement_path, "---\nid: REQ-001\nstatus: draft\n---\n"
    )
    timeout_cmd = "python3 -c 'import time; time.sleep(0.2)'"
    timed_out = evaluate_merge_gate(
        GateRequest(
            base, worktree_dir, agent, None, timeout_cmd, [requirement_path], 0.01
        )
    )
    assert timed_out.findings[0].rule_id == "GATE_VERIFY_CMD_TIMEOUT"


@traces("REQ-002", "AC-03", "SPEC-002")
def test_parallel_scheduler_and_dirty_subgraph(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify conflict-free parallel batch selection and dirty subgraph traversal."""
    _write_document(
        tmp_path / "artifacts/requirements/REQ-001.md",
        "---\nid: REQ-001\nstatus: approved\n---\n",
    )
    _write_document(
        tmp_path / "artifacts/specifications/SPEC-001.md",
        "---\nid: SPEC-001\nstatus: approved\ntraces_to: [REQ-001]\n---\n",
    )
    for task_id, status, dependencies, required_files, write_files in (
        ("TASK-001", "planned", "[]", "[]", "[tests/t1.py]"),
        ("TASK-002", "planned", "[]", "[]", "[tests/t1.py]"),
        ("TASK-003", "planned", "[]", "[]", "[tests/t2.py]"),
        ("TASK-004", "planned", "[TASK-001]", "[tests/t1.py]", "[src/s1.py]"),
        ("TASK-005", "done", "[]", "[]", "[tests/t3.py]"),
        ("TASK-006", "planned", "[TASK-005]", "[tests/missing.py]", "[src/s2.py]"),
    ):
        _write_document(
            tmp_path / f"artifacts/tasks/{task_id}.md",
            f"---\nid: {task_id}\nstatus: {status}\ntraces_to: [SPEC-001]\n"
            f"depends_on: {dependencies}\nrequired_files: {required_files}\n"
            f"write_files: {write_files}\n---\n",
        )
    batch, locks = select_parallel_batch(tmp_path)
    assert batch == ["TASK-001", "TASK-003"] and locks == {"tests/t1.py", "tests/t2.py"}
    dirty = compute_dirty_subgraph(tmp_path, "REQ-001")
    assert dirty == ["SPEC-001", *(f"TASK-00{num}" for num in range(1, 7))]
    assert main(["schedule", "--root", str(tmp_path)]) == 0
    assert "TASK-001\nTASK-003\n" in capsys.readouterr().out
    assert main(["impact", "REQ-001", "--root", str(tmp_path)]) == 0
    assert "SPEC-001" in capsys.readouterr().out


@traces("REQ-002", "AC-04", "SPEC-002")
@traces("REQ-050", "AC-03", "SPEC-050")
@pytest.mark.parametrize(
    ("category", "reroutes", "expected_actor", "expected_status"),
    [
        ("infeasible_scope", 0, "planner-agent", "routed_to_agent"),
        ("infeasible_scope", 1, "human", "awaiting_human"),
        ("test_contract_defect", 0, "review-agent", "routed_to_agent"),
        ("ambiguity", 0, "human", "awaiting_human"),
        ("rule_conflict", 0, "human", "awaiting_human"),
        ("review_exhausted", 0, "human", "awaiting_human"),
    ],
)
def test_escalation_router_and_loop_prevention(
    tmp_path: Path,
    category: str,
    reroutes: int,
    expected_actor: str,
    expected_status: str,
) -> None:
    """Verify deterministic Escalation routing and 1-reroute loop cap."""
    from multi_tasker.orchestrator import router as router_module

    assert not hasattr(router_module, "CATEGORY_ROUTES")
    real_lifecycle = (
        Path(__file__).resolve().parent.parent / "policy/artifact_lifecycle.yaml"
    )
    _write_document(
        tmp_path / "policy/artifact_lifecycle.yaml",
        real_lifecycle.read_text(encoding="utf-8"),
    )
    escalation_relative = "artifacts/escalations/ESC-001.md"
    _write_document(tmp_path / escalation_relative, "no frontmatter\n")
    invalid = route_escalation(tmp_path, escalation_relative)
    assert (invalid.escalation_id, invalid.action) == ("UNKNOWN", "invalid_escalation")
    _write_document(
        tmp_path / escalation_relative,
        f"---\nid: ESC-001\nreason_category: {category}\n---\n",
    )
    decision = route_escalation(tmp_path, escalation_relative, prior_reroutes=reroutes)
    assert (decision.escalation_id, decision.target_actor, decision.next_status) == (
        "ESC-001",
        expected_actor,
        expected_status,
    )


def _seed_extra_artifacts(root: Path) -> None:
    """Seed ESC, DEC, and REV artifacts so all artifact types are exercised."""
    _write_document(
        root / "artifacts/escalations/ESC-001.md",
        "---\nid: ESC-001\nsource_agent: worker-agent\ntask_or_stage: TASK-001\n"
        "affected_artifacts: [REQ-001]\nreason_category: ambiguity\n"
        "status: resolved\nresolved_by: DEC-001\n---\n## Blocking Problem\nText.\n",
    )
    _write_document(
        root / "artifacts/decisions/DEC-001.md",
        "---\nid: DEC-001\nresolves: ESC-001\napplies_to: [REQ-001]\n"
        "status: approved\n---\n## Resolution\nResolved.\n",
    )
    _write_document(
        root / "artifacts/reviews/REV-001.md",
        "---\nid: REV-001\ntarget_artifacts: [REQ-001]\nstage: requirement\n"
        "verdict: pass\nfindings: [ok]\n---\n",
    )


@traces("REQ-001", "AC-05", "SPEC-001")
@traces("REQ-002", "AC-01", "SPEC-002")
@traces("REQ-048", "AC-03", "SPEC-048")
def test_all_policy_yaml_keys_are_enforced_and_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify every enforceable key across all policy/*.yaml files is accessed."""
    repository_root = Path(__file__).resolve().parent.parent
    for folder in ("policy", "artifacts", "src", "tests"):
        shutil.copytree(repository_root / folder, tmp_path / folder)
    _seed_extra_artifacts(tmp_path)
    accessed: set[str] = set()
    defined = set().union(
        *(
            common.collect_policy_keys(load_yaml_file(yaml_file))
            for yaml_file in (tmp_path / "policy").glob("*.yaml")
        )
    )
    for module in POLICY_CONSUMING_MODULES:
        monkeypatch.setattr(
            module,
            "load_yaml_file",
            lambda file_path: common.TrackedPolicyDict(
                load_yaml_file(file_path), accessed
            ),
        )
    assert main(["check", "all", "--root", str(tmp_path)]) == 0
    for role, path in (
        ("requirement-agent", "artifacts/requirements/REQ-001.md"),
        ("specification-agent", "artifacts/specifications/SPEC-001.md"),
        ("planner-agent", "artifacts/tasks/TASK-001.md"),
        ("review-agent", "artifacts/reviews/REV-001.md"),
        ("worker-agent", "artifacts/escalations/ESC-001.md"),
        ("worker-agent", "tests/test_checkers.py"),
        ("worker-agent", "src/multi_tasker/domain/models.py"),
    ):
        task_id = "TASK-001" if path.startswith("tests/") else "TASK-002"
        permissions_checker.check_permissions(tmp_path, role, task_id, [path])
    verify_clean_repository(tmp_path, expected_policy_sha256="check")
    remove_worktree(tmp_path, create_worktree(tmp_path, "spy-wt"))
    metadata_only = {"version", "description", "definition", "category", "id_prefix"}
    assert (defined - accessed) - metadata_only == set()
