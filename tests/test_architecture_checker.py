"""TestContracts for architecture_checker layer and import boundaries."""

import ast
from importlib.metadata import packages_distributions
from pathlib import Path
import re
import sys
import tomllib

import yaml

from multi_tasker.checkers.architecture_checker import check_architecture
from multi_tasker.domain.models import traces
from multi_tasker.domain.parser import load_yaml_file
from multi_tasker.orchestrator.lifecycle import DEFAULT_PYTHON_ARCHITECTURE


def _write_document(path: Path, content: str) -> None:
    """Create parent directories and write file content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _collect_third_party_imports(root: Path, folder: str) -> set[str]:
    """Collect non-stdlib, non-internal top-level imports under folder."""
    internal = {"multi_tasker", "tests", "src"}
    found: set[str] = set()
    for py_path in (root / folder).rglob("*.py"):
        for node in ast.walk(ast.parse(py_path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                found.add(node.module.split(".")[0])
    return found - sys.stdlib_module_names - internal


def _parse_toml_distributions(items: list[str]) -> set[str]:
    """Extract normalized lowercase distribution names from PEP 508 strings."""
    return {re.split(r"[><=~!;\s]", entry)[0].lower() for entry in items}


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
        tmp_path / "policy" / "code_architecture.yaml",
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


@traces("REQ-057", "AC-01", "SPEC-057")
def test_repository_dependency_single_source_of_truth() -> None:
    """Verify 1:1 parity across pyproject.toml, policy, and codebase imports."""
    root = Path(__file__).resolve().parent.parent
    pyproject = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    runtime_dists = _parse_toml_distributions(pyproject["project"]["dependencies"])
    dev_dists = _parse_toml_distributions(
        pyproject["project"]["optional-dependencies"]["dev"]
    )
    dist_to_mods: dict[str, set[str]] = {}
    for mod_name, dist_names in packages_distributions().items():
        if not mod_name.startswith("_"):
            for dist_name in dist_names:
                dist_to_mods.setdefault(dist_name.lower(), set()).add(mod_name)
    runtime_mods = {
        mod for dist in runtime_dists for mod in dist_to_mods.get(dist, {dist})
    }
    src_imports = _collect_third_party_imports(root, "src")
    test_imports = _collect_third_party_imports(root, "tests")
    assert src_imports == runtime_mods
    linters = set(load_yaml_file(root / "policy/code_quality.yaml")["linters"])
    used_dev = {
        dist
        for dist in dev_dists
        if dist in linters
        or (dist.startswith("types-") and dist.removeprefix("types-") in runtime_dists)
        or bool(dist_to_mods.get(dist, {dist}) & test_imports)
    }
    assert dev_dists == used_dev
    arch_policy = load_yaml_file(root / "policy/code_architecture.yaml")
    allowed = list(arch_policy["allowed_third_party_packages"])
    assert "jsonschema" not in allowed
    assert set(allowed) - {"multi_tasker"} == (src_imports | test_imports)
    assert DEFAULT_PYTHON_ARCHITECTURE["allowed_third_party_packages"] == allowed
