"""``Violation`` — one rule hit reported by a workspace gate."""

from __future__ import annotations

from pathlib import Path


class Violation:
    """One rule hit, carrying enough context to print a useful line."""

    __slots__ = ("detail", "lineno", "path", "rule")

    def __init__(self, rule: str, path: Path, lineno: int, detail: str) -> None:
        self.rule = rule
        self.path = path
        self.lineno = lineno
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno}: [{self.rule}] {self.detail}"

    def __repr__(self) -> str:
        return f"Violation({self.rule!r}, {str(self.path)!r}, {self.lineno})"
