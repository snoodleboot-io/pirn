"""One problem found in a documentation file."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DocFinding:
    """A rule violation at ``path:line`` with a human-readable detail."""

    path: str
    line: int
    rule: str
    detail: str

    def render(self) -> str:
        """Format as ``path:line: [rule] detail``."""
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"
