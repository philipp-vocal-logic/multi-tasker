"""Task-scoped and repository-wide JSONL interaction logger under .report/logs/."""

from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any


def _ensure_logs_directory(repository_root: Path) -> Path:
    """Create .report/.gitignore and .report/logs/tasks/ directories."""
    report_directory = repository_root / ".report"
    logs_directory = report_directory / "logs"
    (logs_directory / "tasks").mkdir(parents=True, exist_ok=True)
    gitignore_path = report_directory / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text("*\n", encoding="utf-8")
    return logs_directory


def _extract_flag_value(
    arguments: list[str], flag_names: tuple[str, ...]
) -> str | None:
    """Return value for the first matching CLI flag in arguments."""
    for index, token in enumerate(arguments):
        if token in flag_names and index + 1 < len(arguments):
            return arguments[index + 1]
        for flag in flag_names:
            prefix = f"{flag}="
            if token.startswith(prefix):
                return token[len(prefix) :]
    return None


def _resolve_cli_context(arguments: list[str]) -> dict[str, str | None]:
    """Resolve task_id, agent_role, model, and environment from flags or env."""
    task_id = _extract_flag_value(arguments, ("--task",)) or os.environ.get(
        "MT_TASK_ID"
    )
    agent_role = (
        _extract_flag_value(arguments, ("--agent",))
        or os.environ.get("MT_AGENT_ROLE")
        or "human"
    )
    model = _extract_flag_value(arguments, ("--model",)) or os.environ.get(
        "MT_AGENT_MODEL"
    )
    environment = _extract_flag_value(arguments, ("--environment",)) or os.environ.get(
        "MT_EXECUTION_ENVIRONMENT"
    )
    return {
        "task_id": task_id or None,
        "agent_role": agent_role,
        "model": model or None,
        "environment": environment or None,
    }


def _append_jsonl_record(file_path: Path, record: dict[str, Any]) -> None:
    """Serialize record as deterministic single-line JSON and append to file_path."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(record, sort_keys=True)
    with file_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{serialized}\n")


def record_cli_invocation(
    repository_root: Path,
    command: str,
    arguments: list[str],
    exit_code: int,
    duration_ms: int,
) -> Path:
    """Append a cli_invocation JSONL event to events.jsonl and optional Task log."""
    logs_directory = _ensure_logs_directory(repository_root)
    context = _resolve_cli_context(arguments)
    record: dict[str, Any] = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "event_type": "cli_invocation",
        "command": command,
        "arguments": list(arguments),
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        **context,
    }
    events_path = logs_directory / "events.jsonl"
    _append_jsonl_record(events_path, record)
    task_id = context.get("task_id")
    if task_id:
        _append_jsonl_record(logs_directory / "tasks" / f"{task_id}.jsonl", record)
    return events_path


def record_task_event(
    repository_root: Path,
    task_id: str,
    event_type: str,
    details: dict[str, Any],
    execution_context: tuple[str | None, str, str] | None = None,
    agent_role: str = "worker-agent",
) -> Path:
    """Append a Task execution or MergeGate event to Task and repository logs."""
    logs_directory = _ensure_logs_directory(repository_root)
    environment_name = (
        execution_context[1]
        if execution_context is not None
        else os.environ.get("MT_EXECUTION_ENVIRONMENT")
    )
    model_name = (
        execution_context[2]
        if execution_context is not None
        else os.environ.get("MT_AGENT_MODEL")
    )
    record: dict[str, Any] = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "event_type": event_type,
        "task_id": task_id,
        "agent_role": agent_role,
        "model": model_name or None,
        "environment": environment_name or None,
        "details": details,
    }
    task_log_path = logs_directory / "tasks" / f"{task_id}.jsonl"
    _append_jsonl_record(task_log_path, record)
    _append_jsonl_record(logs_directory / "events.jsonl", record)
    return task_log_path


def _read_jsonl_file(file_path: Path) -> list[dict[str, Any]]:
    """Parse and return all JSON objects from a JSONL file if it exists."""
    if not file_path.is_file():
        return []
    return [
        json.loads(line)
        for line in file_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def read_task_log(repository_root: Path, task_id: str) -> list[dict[str, Any]]:
    """Return parsed JSONL interaction events for task_id."""
    return _read_jsonl_file(
        repository_root / ".report" / "logs" / "tasks" / f"{task_id}.jsonl"
    )


def read_event_log(repository_root: Path) -> list[dict[str, Any]]:
    """Return parsed repository-wide JSONL interaction events."""
    return _read_jsonl_file(repository_root / ".report" / "logs" / "events.jsonl")


def merge_worktree_task_logs(
    repository_root: Path, worktree_path: Path, task_id: str
) -> None:
    """Merge Worktree Task JSONL lines into BaseBranch Task and event logs."""
    worktree_task_log = (
        worktree_path / ".report" / "logs" / "tasks" / f"{task_id}.jsonl"
    )
    if not worktree_task_log.is_file():
        return
    logs_directory = _ensure_logs_directory(repository_root)
    base_task_log = logs_directory / "tasks" / f"{task_id}.jsonl"
    base_events_log = logs_directory / "events.jsonl"
    existing_lines = (
        set(base_task_log.read_text(encoding="utf-8").splitlines())
        if base_task_log.is_file()
        else set()
    )
    new_lines = [
        line
        for line in worktree_task_log.read_text(encoding="utf-8").splitlines()
        if line.strip() and line not in existing_lines
    ]
    if not new_lines:
        return
    joined = "\n".join(new_lines) + "\n"
    with base_task_log.open("a", encoding="utf-8") as task_handle:
        task_handle.write(joined)
    with base_events_log.open("a", encoding="utf-8") as events_handle:
        events_handle.write(joined)


def summarize_pipeline_suitability(
    repository_root: Path,
    completed_ids: list[str] | None = None,
    passed: bool = True,
) -> dict[str, Any]:
    """Aggregate MergeGate pass rate and per-role invocation counts and latencies."""
    events = read_event_log(repository_root)
    invocations = [
        item for item in events if item.get("event_type") == "agent_invocation"
    ]
    gates = [item for item in events if item.get("event_type") == "merge_gate"]
    role_counts: dict[str, int] = {}
    role_durations: dict[str, int] = {}
    for entry in invocations:
        role = str(entry.get("agent_role", "worker-agent"))
        duration = int(entry.get("details", {}).get("duration_ms", 0))
        role_counts[role] = role_counts.get(role, 0) + 1
        role_durations[role] = role_durations.get(role, 0) + duration
    passed_gates = sum(
        1 for entry in gates if entry.get("details", {}).get("passed") is True
    )
    total_gates = len(gates)
    rate = round(passed_gates / total_gates, 4) if total_gates else 0.0
    return {
        "passed": passed,
        "completed_artifacts": list(completed_ids or []),
        "agent_invocations": len(invocations),
        "merge_gate_total": total_gates,
        "merge_gate_passed": passed_gates,
        "gate_pass_rate": rate,
        "role_invocations": role_counts,
        "role_durations_ms": role_durations,
    }
