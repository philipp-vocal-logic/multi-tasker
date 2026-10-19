"""Agent WriteScope and state-based permission checker (`mt check permissions`)."""

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

from multi_tasker.checkers.common import get_git_changed_files
from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import (
    infer_artifact_type,
    load_state_transitions,
    load_yaml_file,
    parse_artifact_file,
)

StateContext = tuple[dict[str, str], dict[str, dict[str, set[str]]]]


def _read_artifact_state(repository_root: Path, relative_path: str) -> str | None:
    """Return frontmatter status of an artifact file if it exists on disk."""
    absolute_path = repository_root / relative_path
    if absolute_path.is_file() and relative_path.startswith("artifacts/"):
        document, _ = parse_artifact_file(absolute_path, relative_path)
        if document and "status" in document.frontmatter:
            return str(document.frontmatter["status"])
    return None


def _matches_any_glob(relative_path: str, globs: list[str]) -> bool:
    """Return True if relative_path matches any glob pattern in globs."""
    return any(fnmatch(relative_path, pattern) for pattern in globs)


def _check_escalation_rule_match(
    repository_root: Path,
    escalation_files: list[str],
    rules: list[dict[str, Any]],
    state_context: StateContext,
) -> list[Finding]:
    """Verify each Escalation file matches an escalation_write rule and state."""
    findings: list[Finding] = []
    for escalation_file in escalation_files:
        matched = next(
            (
                rule
                for rule in rules
                if fnmatch(escalation_file, str(rule.get("path", "")))
            ),
            None,
        )
        if matched is None:
            message = "This agent role is not permitted to emit Escalations."
            findings.append(
                Finding(escalation_file, 1, "PERM_ESC_NOT_ALLOWED", message)
            )
        else:
            findings.extend(
                _check_state_and_create(
                    repository_root, escalation_file, matched, state_context
                )
            )
    return findings


def _check_escalation_exclusivity(
    repository_root: Path,
    changed_files: list[str],
    agent_configuration: dict[str, Any],
    escalation_policy: dict[str, Any],
    state_context: StateContext,
) -> tuple[bool, list[Finding]]:
    """Check if changes are an Escalation and enforce exclusivity rules."""
    rules: list[dict[str, Any]] = agent_configuration.get("escalation_write", [])
    escalation_files = [
        path for path in changed_files if path.startswith("artifacts/escalations/")
    ]
    if not escalation_files:
        return False, []
    findings = _check_escalation_rule_match(
        repository_root, escalation_files, rules, state_context
    )
    max_allowed = int(escalation_policy.get("max_escalation_files_per_run", 1))
    forbid_domain = bool(
        escalation_policy.get("forbid_domain_writes_when_escalating", True)
    )
    if len(escalation_files) > max_allowed:
        message = f"At most {max_allowed} Escalation file(s) may be emitted per run."
        findings.append(
            Finding(escalation_files[max_allowed], 1, "PERM_ESC_MULTIPLE", message)
        )
    other_files = [path for path in changed_files if path not in escalation_files]
    if other_files and forbid_domain:
        message = f"Cannot modify '{other_files[0]}' when escalating."
        findings.append(Finding(other_files[0], 1, "PERM_ESC_EXCLUSIVITY", message))
    return True, findings


def _resolve_task_write_scope(
    repository_root: Path, task_id: str | None, rule: dict[str, Any]
) -> tuple[list[str], list[Finding]]:
    """Load TASK-NNN.md and verify task state and task_type_path_constraints."""
    if not task_id:
        message = "worker-agent requires --task ID."
        return [], [
            Finding("policy/permissions.yaml", 1, "PERM_TASK_ID_MISSING", message)
        ]
    task_relative = f"artifacts/tasks/{task_id}.md"
    task_absolute = repository_root / task_relative
    if not task_absolute.exists():
        message = f"Task file '{task_relative}' does not exist."
        return [], [Finding(task_relative, 1, "PERM_TASK_NOT_FOUND", message)]
    document, parse_findings = parse_artifact_file(task_absolute, task_relative)
    if parse_findings or document is None:
        return [], parse_findings
    findings: list[Finding] = []
    required_state = rule.get("require_task_state")
    actual_state = document.frontmatter.get("status")
    if required_state and actual_state != required_state:
        message = (
            f"Task '{task_id}' status is '{actual_state}', expected '{required_state}'."
        )
        findings.append(Finding(task_relative, 1, "PERM_TASK_STATE", message))
    write_files = [str(item) for item in document.frontmatter.get("write_files", [])]
    task_type = str(document.frontmatter.get("type", ""))
    allowed_globs = rule.get("task_type_path_constraints", {}).get(task_type, [])
    for write_file in write_files:
        if allowed_globs and not _matches_any_glob(write_file, allowed_globs):
            message = (
                f"Task '{task_id}' (type '{task_type}') cannot write to '{write_file}'."
            )
            findings.append(
                Finding(task_relative, 1, "PERM_LOCKED_TEST_CONTRACT", message)
            )
    return write_files, findings


def _check_target_and_transition(
    relative_path: str,
    rule: dict[str, Any],
    old_state: str | None,
    new_state: str | None,
    transitions: dict[str, dict[str, set[str]]],
) -> list[Finding]:
    """Enforce allowed_target_states and state_transitions for an artifact."""
    allowed_targets = rule.get("allowed_target_states")
    if new_state is None:
        return []
    if isinstance(allowed_targets, list) and new_state not in allowed_targets:
        message = f"Target state '{new_state}' not in {allowed_targets}."
        return [Finding(relative_path, 1, "PERM_INVALID_TARGET_STATE", message)]
    artifact_map = transitions.get(infer_artifact_type(relative_path))
    if (
        old_state
        and old_state != new_state
        and artifact_map is not None
        and new_state not in artifact_map.get(old_state, set())
    ):
        message = f"Invalid state transition '{old_state}' -> '{new_state}'."
        return [Finding(relative_path, 1, "PERM_INVALID_STATE_TRANSITION", message)]
    return []


def _check_state_and_create(
    repository_root: Path,
    relative_path: str,
    rule: dict[str, Any],
    state_context: StateContext,
) -> list[Finding]:
    """Enforce allow_create, existing state, target state, and transition rules."""
    existing_states, transitions = state_context
    allowed_states = rule.get("allowed_existing_states")
    new_state = _read_artifact_state(repository_root, relative_path)
    old_state = existing_states.get(relative_path)
    errors = _check_target_and_transition(
        relative_path, rule, old_state, new_state, transitions
    )
    if relative_path not in existing_states:
        if rule.get("allow_create", True) is False:
            message = f"Creating new file '{relative_path}' is not permitted."
            return [
                Finding(relative_path, 1, "PERM_CREATE_FORBIDDEN", message),
                *errors,
            ]
        return errors
    if isinstance(allowed_states, list) and old_state not in allowed_states:
        message = f"Cannot modify '{relative_path}' in state '{old_state}'."
        return [Finding(relative_path, 1, "PERM_INVALID_STATE_EDIT", message), *errors]
    return errors


def _verify_file_against_rules(
    repository_root: Path,
    relative_path: str,
    rules: list[dict[str, Any]],
    task_id: str | None,
    state_context: StateContext,
) -> list[Finding]:
    """Verify a single changed file against agent allowed_write rules."""
    findings: list[Finding] = []
    for rule in rules:
        pattern = str(rule.get("path", ""))
        if pattern == "$TASK_WRITE_FILES":
            task_globs, task_errors = _resolve_task_write_scope(
                repository_root, task_id, rule
            )
            findings.extend(task_errors)
            lock_tests = bool(rule.get("forbid_locked_test_contracts"))
            has_tests = any(fnmatch(glob_item, "tests/**") for glob_item in task_globs)
            if lock_tests and relative_path.startswith("tests/") and not has_tests:
                message = f"Locked TestContract '{relative_path}' cannot be modified."
                findings.append(
                    Finding(relative_path, 1, "PERM_LOCKED_TEST_CONTRACT", message)
                )
            if relative_path in task_globs:
                errors = _check_state_and_create(
                    repository_root, relative_path, rule, state_context
                )
                return [*findings, *errors]
        elif fnmatch(relative_path, pattern):
            errors = _check_state_and_create(
                repository_root, relative_path, rule, state_context
            )
            return [*findings, *errors]
    message = f"File '{relative_path}' is outside agent WriteScope."
    return [*findings, Finding(relative_path, 1, "PERM_OUTSIDE_WRITE_SCOPE", message)]


def _check_empty_task_scope(
    repository_root: Path, rules: list[dict[str, Any]], task_id: str | None
) -> list[Finding]:
    """Validate task_id scope up front when rules use $TASK_WRITE_FILES."""
    return [
        finding
        for rule in rules
        if rule.get("path") == "$TASK_WRITE_FILES"
        for finding in _resolve_task_write_scope(repository_root, task_id, rule)[1]
    ]


def _evaluate_role_permissions(
    repository_root: Path,
    files: list[str],
    policy: dict[str, Any],
    agent_configuration: dict[str, Any],
    context: tuple[str | None, dict[str, str]],
) -> list[Finding]:
    """Evaluate global forbidden, read_scope, escalation, and write rules."""
    task_id, states = context
    state_context = (states, load_state_transitions(repository_root, policy))
    forbidden: list[str] = policy.get("global_forbidden_write", [])
    read_globs = [str(item) for item in agent_configuration.get("read_scope", ["**/*"])]
    findings = [
        Finding(path, 1, "PERM_FORBIDDEN_PATH", "Globally forbidden path.")
        for path in files
        if _matches_any_glob(path, forbidden)
    ] + [
        Finding(path, 1, "PERM_OUTSIDE_READ_SCOPE", "Path outside read_scope.")
        for path in files
        if not _matches_any_glob(path, read_globs)
    ]
    escalation_policy: dict[str, Any] = policy.get("escalation_exclusivity", {})
    is_escalation, escalation_errors = _check_escalation_exclusivity(
        repository_root, files, agent_configuration, escalation_policy, state_context
    )
    findings.extend(escalation_errors)
    if not is_escalation:
        rules: list[dict[str, Any]] = agent_configuration.get("allowed_write", [])
        if not files:
            findings.extend(_check_empty_task_scope(repository_root, rules, task_id))
        for relative_path in files:
            findings.extend(
                _verify_file_against_rules(
                    repository_root, relative_path, rules, task_id, state_context
                )
            )
    return findings


def _validate_agent_execution_settings(policy: dict[str, Any]) -> bool:
    """Return True if all agents have valid model and worktree_execution values."""
    agents: dict[str, Any] = policy.get("agents", {})
    for agent_config in agents.values():
        if not isinstance(agent_config, dict):
            continue
        model_val = agent_config.get("model", "default")
        worktree_flag = agent_config.get("worktree_execution", True)
        if (
            not isinstance(model_val, str)
            or not model_val.strip()
            or not isinstance(worktree_flag, bool)
        ):
            return False
    return True


def _validate_execution_environments(policy: dict[str, Any]) -> list[Finding]:
    """Validate execution_environments and per-agent settings in permissions.yaml."""
    if not _validate_agent_execution_settings(policy):
        message = "Invalid agent execution settings in policy/permissions.yaml."
        return [Finding("policy/permissions.yaml", 1, "PERM_INVALID_EXEC_ENV", message)]
    execution_config: dict[str, Any] = policy.get("execution_environments", {})
    if not execution_config:
        return []
    default_env = str(execution_config.get("default_environment", ""))
    default_model = str(execution_config.get("default_model", ""))
    default_mode = str(execution_config.get("default_context_mode", "inline"))
    environments: dict[str, Any] = execution_config.get("environments", {})
    templates = {str(name): str(command) for name, command in environments.items()}
    invalid_env = bool(default_env and default_env not in templates)
    if invalid_env or not default_model or default_mode not in {"inline", "paths"}:
        message = "Invalid execution_environments in policy/permissions.yaml."
        return [Finding("policy/permissions.yaml", 1, "PERM_INVALID_EXEC_ENV", message)]
    return []


def _check_unscoped_policy_writes(files: list[str]) -> list[Finding]:
    """Return findings for protected policy files modified without an agent role."""
    return [
        Finding(path, 1, "PERM_POLICY_MODIFIED", "Protected policy modified.")
        for path in files
        if fnmatch(path, "policy/**")
    ]


def check_permissions(
    repository_root: Path,
    agent_role: str | None = None,
    task_id: str | None = None,
    changed_files: list[str] | None = None,
    existing_states: dict[str, str] | None = None,
) -> list[Finding]:
    """Enforce policy/permissions.yaml on changed files and agent role."""
    permissions_path = repository_root / "policy" / "permissions.yaml"
    if not permissions_path.exists():
        message = "Missing policy/permissions.yaml."
        return [Finding("policy/permissions.yaml", 1, "PERM_POLICY_MISSING", message)]
    policy = load_yaml_file(permissions_path)
    environment_findings = _validate_execution_environments(policy)
    task_marker = (
        f"artifacts/tasks/{task_id}.md"
        if agent_role == "worker-agent" and task_id
        else ""
    )
    files = (
        changed_files
        if changed_files is not None
        else [
            path
            for path in get_git_changed_files(repository_root)
            if path != task_marker
        ]
    )
    if agent_role is None:
        return [*environment_findings, *_check_unscoped_policy_writes(files)]
    agents_configuration: dict[str, Any] = policy.get("agents", {})
    if agent_role not in agents_configuration:
        message = f"Unknown agent role '{agent_role}'."
        return [Finding("policy/permissions.yaml", 1, "PERM_UNKNOWN_AGENT", message)]
    role_findings = _evaluate_role_permissions(
        repository_root,
        files,
        policy,
        agents_configuration[agent_role],
        (task_id, existing_states or {}),
    )
    return [*environment_findings, *role_findings]
