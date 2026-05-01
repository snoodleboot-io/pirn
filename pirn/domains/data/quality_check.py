"""One-line quality assertion result."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QualityCheck:
    """A single quality assertion's outcome.

    Threshold and observed values are kept as strings so audit logs can
    serialise them unambiguously regardless of source type.
    """

    name: str
    passed: bool
    threshold: str
    actual: str
    column: str | None = None
