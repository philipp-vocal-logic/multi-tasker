"""Language preset scaffolding and prompt templates for Python, ANSI C, and Rust."""

from pathlib import Path
from typing import Any

import yaml

from multi_tasker.domain.parser import load_yaml_file

VALID_PRESETS = ("python", "ansi-c", "rust", "multi-tasker")

_PRESET_SETTINGS: dict[str, dict[str, Any]] = {
    "ansi-c": {
        "extensions": [".c", ".h"],
        "forbidden_calls": ["printf", "gets"],
        "test_glob": "test_*.c",
        "test_cmd": (
            "gcc -std=c89 -pedantic -Wall -Wextra -Werror "
            "-fsyntax-only -Isrc <test_file>"
        ),
        "impl_cmd": (
            "sh -c 'gcc -std=c89 -pedantic -Wall -Wextra -Werror -Isrc "
            "<test_file> src/domain/*.c -o .report/test_runner && .report/test_runner'"
        ),
        "test_pattern": r"^tests/.+\.(c|h)$",
        "impl_pattern": r"^src/.+\.(c|h)$",
        "domain_paths": ["src/domain/**", "src/*.c", "src/*.h"],
        "ephemeral": ["build/**", "**/*.o", "**/*.a", "**/*.out"],
    },
    "rust": {
        "extensions": [".rs"],
        "forbidden_calls": ["println", "dbg"],
        "test_glob": "test_*.rs",
        "test_cmd": (
            "rustfmt --check --edition 2021 --config skip_children=true <test_file>"
        ),
        "impl_cmd": (
            "sh -c 'rustc --edition 2021 --test <test_file> "
            "-o .report/test_runner && .report/test_runner --quiet'"
        ),
        "test_pattern": r"^tests/.+\.rs$",
        "impl_pattern": r"^src/.+\.rs$",
        "domain_paths": ["src/domain/**", "src/*.rs"],
        "ephemeral": ["target/**", "**/*.rlib", "**/*.rmeta"],
    },
}


def _update_yaml_policy(policy_path: Path, updater: Any) -> None:
    """Load policy_path if present, mutate via updater, and write back."""
    if not policy_path.is_file():
        return
    data = load_yaml_file(policy_path)
    updater(data)
    policy_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _apply_quality_and_trace_preset(
    policy_dir: Path, preset: str, cfg: dict[str, Any]
) -> None:
    """Update code_quality.yaml and traceability.yaml for preset."""

    def _mutate_quality(data: dict[str, Any]) -> None:
        data["language"] = preset
        data["source_extensions"] = list(cfg["extensions"])
        for linter in data.get("linters", {}).values():
            if isinstance(linter, dict):
                linter["enabled"] = False
        ast_rules = data.setdefault("ast_rules", {})
        ast_rules["forbidden_calls_in_src"] = list(cfg["forbidden_calls"])

    def _mutate_traceability(data: dict[str, Any]) -> None:
        rules = data.setdefault("traceability_rules", {})
        rules["test_file_glob"] = cfg["test_glob"]
        rules["test_contract_verification_cmd"] = cfg["test_cmd"]
        rules["implementation_verification_cmd"] = cfg["impl_cmd"]

    _update_yaml_policy(policy_dir / "code_quality.yaml", _mutate_quality)
    _update_yaml_policy(policy_dir / "traceability.yaml", _mutate_traceability)


def _apply_schema_and_arch_preset(policy_dir: Path, cfg: dict[str, Any]) -> None:
    """Update schemas, architecture, and execution policy YAML files for preset."""

    def _mutate_schemas(data: dict[str, Any]) -> None:
        props = (
            data.get("schemas", {})
            .get("SPEC", {})
            .get("json_schema", {})
            .get("properties", {})
            .get("target_files", {})
            .get("properties", {})
        )
        if "tests" in props:
            props["tests"]["items"]["pattern"] = cfg["test_pattern"]
        if "implementation" in props:
            props["implementation"]["items"]["pattern"] = cfg["impl_pattern"]

    def _mutate_architecture(data: dict[str, Any]) -> None:
        layers = data.get("layers", [])
        if layers and isinstance(layers[0], dict):
            layers[0]["paths"] = list(cfg["domain_paths"])

    def _mutate_execution(data: dict[str, Any]) -> None:
        invariants = data.setdefault("clean_repo_invariants", {})
        globs = list(invariants.get("ignored_ephemeral_globs", []))
        invariants["ignored_ephemeral_globs"] = [
            *globs,
            *(item for item in cfg["ephemeral"] if item not in globs),
        ]

    _update_yaml_policy(policy_dir / "artifact_schemas.yaml", _mutate_schemas)
    _update_yaml_policy(policy_dir / "code_architecture.yaml", _mutate_architecture)
    _update_yaml_policy(policy_dir / "agent_execution.yaml", _mutate_execution)


def apply_language_preset_policies(repository_root: Path, preset: str) -> None:
    """Tailor scaffolded policy/*.yaml files when preset is ansi-c or rust."""
    if preset not in _PRESET_SETTINGS:
        return
    cfg = _PRESET_SETTINGS[preset]
    policy_dir = repository_root / "policy"
    _apply_quality_and_trace_preset(policy_dir, preset, cfg)
    _apply_schema_and_arch_preset(policy_dir, cfg)


def code_fence_for_path(relative_path: str) -> str:
    """Return Markdown code fence language identifier for relative_path."""
    if relative_path.endswith(".md"):
        return "markdown"
    if relative_path.endswith((".c", ".h")):
        return "c"
    if relative_path.endswith(".rs"):
        return "rust"
    return "python"


def _load_configured_language(repository_root: Path | None) -> str:
    """Read configured language from policy/code_quality.yaml."""
    if repository_root is None:
        return "python"
    quality_path = repository_root / "policy" / "code_quality.yaml"
    if not quality_path.is_file():
        return "python"
    return str(load_yaml_file(quality_path).get("language", "python"))


def _render_non_python_worker_contract(language: str) -> list[str]:
    """Render ANSI C or Rust Source & TestContract skeleton for worker."""
    if language == "ansi-c":
        return [
            "### ANSI C Source & `TestContract` Output Contract (`Allowed Write`)",
            "```c",
            "/** Concise doc comment within max_docstring_lines/words. */",
            "#include <assert.h>",
            "",
            '/* @traces("REQ-NNN", "AC-XX", "SPEC-NNN") */',
            "void test_example_behavior(void) {",
            "    int expected_value = 1;",
            "    assert(expected_value == 1);",
            "}",
            "```",
            "- **Scope & Standards**: Write strict ANSI C89 (`.c`/`.h`) within "
            "`Allowed Write` with identifiers `>= min_identifier_length` chars.",
            "",
        ]
    return [
        "### Rust Source & `TestContract` Output Contract (`Allowed Write`)",
        "```rust",
        "//! Concise module doc comment within max_docstring_lines/words.",
        "",
        '// @traces("REQ-NNN", "AC-XX", "SPEC-NNN")',
        "#[test]",
        "fn test_example_behavior() {",
        "    let expected_value = 1;",
        "    assert_eq!(expected_value, 1);",
        "}",
        "```",
        "- **Scope & Standards**: Write Rust 2021 (`.rs`) within `Allowed Write` "
        "with explicit return types and names `>= min_identifier_length` chars.",
        "",
    ]


def render_language_worker_contract(repository_root: Path | None = None) -> list[str]:
    """Render Python, ANSI C, or Rust Source & TestContract skeleton for worker."""
    language = _load_configured_language(repository_root)
    if language in {"ansi-c", "rust"}:
        return _render_non_python_worker_contract(language)
    return [
        "### Python Source & `TestContract` Output Contract (`Allowed Write`)",
        "```python",
        '"""Single-paragraph module docstring within max_docstring_lines/words."""',
        "",
        "from multi_tasker.domain.models import traces",
        "",
        "",
        '@traces("REQ-NNN", "AC-XX", "SPEC-NNN")',
        "def test_example_behavior() -> None:",
        '    """Single-paragraph docstring (return type, names >= 3 chars)."""',
        "    expected_value = 1",
        "    assert expected_value == 1",
        "```",
        "- **Scope & Imports**: Create or update only the exact path(s) in "
        "`Allowed Write` (parent directories are created automatically; `src` and `.` "
        "are on `PYTHONPATH`, so namespace imports work without extra `__init__.py` "
        "files).",
        "- **Docstrings & Types**: Keep every module, class, and function docstring "
        "within `max_docstring_lines` and `max_docstring_words`; declare explicit "
        "return types (`-> None`, `-> int`, etc.) and use identifiers "
        "`>= min_identifier_length` chars.",
        "",
    ]
