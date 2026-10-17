"""Zero-noise CLI entrypoint for `mt`."""

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Any

from src.checkers.runner import ALL_CHECKS, run_checks
from src.cli.output import emit_findings
from src.domain.models import Finding
from src.orchestrator.documentation_generator import (
    write_repository_documentation,
)
from src.orchestrator.interaction_logger import record_cli_invocation
from src.orchestrator.lifecycle import (
    approve_artifact,
    create_intent,
    initialize_repository,
    resolve_escalation,
)
from src.orchestrator.lineage import trace_lineage
from src.orchestrator.prompt_builder import VALID_CONTEXT_MODES, build_agent_prompt
from src.orchestrator.scheduler import compute_dirty_subgraph, select_parallel_batch
from src.orchestrator.task_runner import run_scheduled_tasks


def _add_lifecycle_parsers(subparsers: Any) -> None:
    """Register initialize, intent, approve, resolve, run, trace, and documentation."""
    for name in ("initialize", "documentation"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--root", default=".", help="Repository root directory.")
    for name, argument_name in (
        ("intent", "text"),
        ("approve", "artifact_id"),
        ("trace", "target"),
    ):
        subparser = subparsers.add_parser(name)
        subparser.add_argument(argument_name)
        subparser.add_argument("--root", default=".", help="Repository root directory.")
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("escalation_id", help="ESC-NNN identifier.")
    resolve_parser.add_argument("--by", required=True, dest="resolved_by")
    resolve_parser.add_argument(
        "--root", default=".", help="Repository root directory."
    )
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--max-workers", type=int, default=1)
    run_parser.add_argument("--agent-command", default=None, dest="agent_command")
    run_parser.add_argument("--model", default=None, dest="model")
    run_parser.add_argument("--environment", default=None, dest="environment")
    run_parser.add_argument("--context-mode", default=None, dest="context_mode")
    run_parser.add_argument("--root", default=".", help="Repository root directory.")
    prompt_parser = subparsers.add_parser("prompt")
    prompt_parser.add_argument("agent_role", help="Canonical agent role.")
    prompt_parser.add_argument("--target", default=None, dest="target_id")
    prompt_parser.add_argument("--context-mode", default=None, dest="context_mode")
    prompt_parser.add_argument("--root", default=".", help="Repository root directory.")


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for `mt` CLI."""
    parser = argparse.ArgumentParser(prog="mt", add_help=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    check_parser = subparsers.add_parser(
        "check", help="Run deterministic policy checks."
    )
    check_parser.add_argument(
        "checks",
        nargs="*",
        default=["all"],
        help=f"Checks to run: all, {', '.join(ALL_CHECKS)}",
    )
    check_parser.add_argument("--agent", dest="agent_role", default=None)
    check_parser.add_argument("--task", dest="task_id", default=None)
    check_parser.add_argument("--paths", nargs="*", default=None)
    check_parser.add_argument("--root", default=".", help="Repository root directory.")
    schedule_parser = subparsers.add_parser(
        "schedule", help="List conflict-free parallel Task batch."
    )
    schedule_parser.add_argument(
        "--root", default=".", help="Repository root directory."
    )
    impact_parser = subparsers.add_parser(
        "impact", help="List downstream dirty-flagged artifacts."
    )
    impact_parser.add_argument(
        "artifact_id", help="Changed Requirement or Decision ID."
    )
    impact_parser.add_argument("--root", default=".", help="Repository root directory.")
    _add_lifecycle_parsers(subparsers)
    return parser


def _run_check_command(arguments: argparse.Namespace) -> int:
    """Execute `mt check` and write Findings-only output."""
    repository_root = Path(arguments.root).resolve()
    findings = run_checks(
        repository_root=repository_root,
        check_names=list(arguments.checks),
        target_paths=arguments.paths,
        agent_role=arguments.agent_role,
        task_id=arguments.task_id,
    )
    return emit_findings(repository_root, findings)


def _invoke_with_context_mode(
    repository_root: Path, arguments: argparse.Namespace
) -> tuple[list[str], list[Finding]]:
    """Run scheduled tasks with temporary MT_CONTEXT_MODE override when provided."""
    context_mode = getattr(arguments, "context_mode", None)
    previous_mode = os.environ.get("MT_CONTEXT_MODE")
    if context_mode is not None:
        os.environ["MT_CONTEXT_MODE"] = str(context_mode)
    try:
        return run_scheduled_tasks(
            repository_root,
            int(arguments.max_workers),
            arguments.agent_command,
            arguments.model,
            arguments.environment,
        )
    finally:
        if context_mode is not None:
            if previous_mode is None:
                os.environ.pop("MT_CONTEXT_MODE", None)
            else:
                os.environ["MT_CONTEXT_MODE"] = previous_mode


def _run_tasks_command(repository_root: Path, arguments: argparse.Namespace) -> int:
    """Execute `mt run` and output completed Task IDs or Findings."""
    context_mode = getattr(arguments, "context_mode", None)
    if context_mode is not None and str(context_mode) not in VALID_CONTEXT_MODES:
        message = f"Invalid context_mode '{context_mode}'."
        finding = Finding(
            "policy/permissions.yaml", 1, "CLI_INVALID_CONTEXT_MODE", message
        )
        return emit_findings(repository_root, [finding])
    done_ids, findings = _invoke_with_context_mode(repository_root, arguments)
    if findings:
        return emit_findings(repository_root, findings)
    for task_id in done_ids:
        sys.stdout.write(f"{task_id}\n")
    return 0


def _run_prompt_command(repository_root: Path, arguments: argparse.Namespace) -> int:
    """Execute `mt prompt` and write synthesized role prompt or Findings."""
    prompt_text, findings = build_agent_prompt(
        repository_root,
        str(arguments.agent_role),
        arguments.target_id,
        getattr(arguments, "context_mode", None),
    )
    if findings:
        return emit_findings(repository_root, findings)
    sys.stdout.write(prompt_text)
    return 0


def _dispatch_lifecycle(
    command: str, arguments: argparse.Namespace, repository_root: Path
) -> int:
    """Dispatch initialize, intent, approve, resolve, run, trace, or documentation."""
    if command == "initialize":
        return emit_findings(repository_root, initialize_repository(repository_root))
    if command == "intent":
        sys.stdout.write(f"{create_intent(repository_root, str(arguments.text))}\n")
        return 0
    if command == "approve":
        return emit_findings(
            repository_root,
            approve_artifact(repository_root, str(arguments.artifact_id)),
        )
    if command == "resolve":
        findings = resolve_escalation(
            repository_root,
            str(arguments.escalation_id),
            str(arguments.resolved_by),
        )
        return emit_findings(repository_root, findings)
    if command == "run":
        return _run_tasks_command(repository_root, arguments)
    if command == "documentation":
        sys.stdout.write(
            write_repository_documentation(repository_root).read_text(encoding="utf-8")
        )
        return 0
    for line in trace_lineage(repository_root, str(arguments.target)):
        sys.stdout.write(f"{line}\n")
    return 0


def _execute_command(arguments: argparse.Namespace, repository_root: Path) -> int:
    """Dispatch parsed CLI arguments and return process exit code."""
    if arguments.command == "check":
        return _run_check_command(arguments)
    if arguments.command == "prompt":
        return _run_prompt_command(repository_root, arguments)
    if arguments.command == "schedule":
        batch, _ = select_parallel_batch(repository_root)
        for task_id in batch:
            sys.stdout.write(f"{task_id}\n")
        return 0
    if arguments.command == "impact":
        for artifact_id in compute_dirty_subgraph(
            repository_root, str(arguments.artifact_id)
        ):
            sys.stdout.write(f"{artifact_id}\n")
        return 0
    return _dispatch_lifecycle(str(arguments.command), arguments, repository_root)


def main(argument_values: list[str] | None = None) -> int:
    """Execute CLI command, record interaction log, and emit low-noise output."""
    raw_arguments = (
        list(argument_values) if argument_values is not None else sys.argv[1:]
    )
    arguments = build_parser().parse_args(raw_arguments)
    repository_root = Path(arguments.root).resolve()
    started_at = time.monotonic()
    exit_code = _execute_command(arguments, repository_root)
    duration_ms = int((time.monotonic() - started_at) * 1000)
    record_cli_invocation(
        repository_root,
        str(arguments.command),
        raw_arguments,
        exit_code,
        duration_ms,
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
