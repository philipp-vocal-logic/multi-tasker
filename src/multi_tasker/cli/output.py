"""Zero-noise CLI output contract loader and Finding formatter."""

from pathlib import Path
import sys

from multi_tasker.domain.models import Finding
from multi_tasker.domain.parser import load_yaml_file


def load_output_contract(repository_root: Path) -> tuple[bool, str]:
    """Load silent_on_pass and finding_format from policy/code_quality.yaml."""
    default_format = "{path}:{line}: [{rule_id}] {message}"
    configuration_path = repository_root / "policy" / "code_quality.yaml"
    if not configuration_path.exists():
        return True, default_format
    contract = load_yaml_file(configuration_path).get("output_contract", {})
    silent_on_pass = bool(contract.get("silent_on_pass", True))
    finding_format = str(contract.get("finding_format", default_format))
    return silent_on_pass, finding_format


def load_remediation_hints(repository_root: Path) -> dict[str, str]:
    """Load rule_id to remediation hint mappings from all policy/*.yaml files."""
    policy_directory = repository_root / "policy"
    if not policy_directory.is_dir():
        return {}
    hints: dict[str, str] = {}
    for policy_file in sorted(policy_directory.glob("*.yaml")):
        remediation = load_yaml_file(policy_file).get("remediation", {})
        if isinstance(remediation, dict):
            for rule_id, hint in remediation.items():
                hints[str(rule_id)] = str(hint)
    return hints


def emit_findings(repository_root: Path, findings: list[Finding]) -> int:
    """Write Findings according to output_contract and return exit code 0 or 1."""
    silent_on_pass, finding_format = load_output_contract(repository_root)
    hints = load_remediation_hints(repository_root)
    if not findings:
        if not silent_on_pass:
            sys.stdout.write("OK\n")
        return 0
    seen_rules: set[str] = set()
    for item in findings:
        formatted = item.format(finding_format)
        hint = hints.get(item.rule_id)
        if hint and item.rule_id not in seen_rules:
            formatted = f"{formatted} (Hint: {hint})"
            seen_rules.add(item.rule_id)
        sys.stdout.write(f"{formatted}\n")
    return 1
