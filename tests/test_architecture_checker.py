"""TestContracts for architecture_checker layer and import boundaries."""

from pathlib import Path

import yaml

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.domain.models import traces


def _write_document(path: Path, content: str) -> None:
    """Create parent directories and write file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@traces("REQ-001", "AC-03", "SPEC-001")
def test_architecture_checker_violation_branches(tmp_path: Path) -> None:
    """Verify architecture circular, third-party, and layer rules."""
    assert check_architecture(tmp_path)[0].rule_id == "ARCH_POLICY_MISSING"
    layer_configuration = {
        "name": "dom",
        "paths": ["src/domain/**"],
        "allowed_internal_imports": ["src.domain"],
    }
    _write_document(
        tmp_path / "policy" / "architecture.yaml",
        yaml.safe_dump(
            {
                "dependency_rules": {"forbid_circular_imports": True},
                "allowed_third_party_packages": [],
                "layers": [layer_configuration],
            }
        ),
    )
    _write_document(
        tmp_path / "src" / "domain" / "a.py",
        "import ext_pkg\nfrom . import b\nfrom ..cli import main\n",
    )
    _write_document(tmp_path / "src" / "domain" / "b.py", "from .a import run\n")
    _write_document(tmp_path / "src" / "other.py", "val = 1\n")
    architecture_rules = {finding.rule_id for finding in check_architecture(tmp_path)}
    assert {
        "ARCH_THIRD_PARTY_FORBIDDEN",
        "ARCH_FORBIDDEN_IMPORT",
        "ARCH_CIRCULAR_IMPORT",
        "ARCH_UNKNOWN_LAYER",
    }.issubset(architecture_rules)
    scoped = {
        finding.rule_id for finding in check_architecture(tmp_path, ["src/other.py"])
    }
    assert "ARCH_UNKNOWN_LAYER" in scoped
