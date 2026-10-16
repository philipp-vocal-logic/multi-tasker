"""Core domain data structures for Findings, Artifacts, and Traceability."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

FunctionType = TypeVar("FunctionType", bound=Callable[..., Any])


@dataclass(frozen=True, order=True)
class Finding:
    """Single-line policy violation emitted by a deterministic checker."""

    path: str
    line: int
    rule_id: str
    message: str

    def format(self, template: str = "{path}:{line}: [{rule_id}] {message}") -> str:
        """Format Finding using the configured output_contract template."""
        return template.format(
            path=self.path,
            line=self.line,
            rule_id=self.rule_id,
            message=self.message,
        )


@dataclass(frozen=True)
class SectionSlice:
    """Markdown section content and starting line number."""

    name: str
    start_line: int
    content: str


@dataclass(frozen=True)
class ArtifactDocument:
    """Parsed Markdown artifact with YAML frontmatter and body sections."""

    path: str
    artifact_type: str
    frontmatter: dict[str, Any]
    body: str
    body_start_line: int
    sections: dict[str, SectionSlice]


def traces(
    requirement_id: str, criterion_id: str, specification_id: str
) -> Callable[[FunctionType], FunctionType]:
    """Attach Requirement, AcceptanceCriterion, and Specification metadata."""

    def decorator(function: FunctionType) -> FunctionType:
        attribute_name = "__traces__"
        existing: list[tuple[str, str, str]] = getattr(function, attribute_name, [])
        setattr(
            function,
            attribute_name,
            [*existing, (requirement_id, criterion_id, specification_id)],
        )
        return function

    return decorator
