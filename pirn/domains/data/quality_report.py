"""Aggregate report emitted by quality knots."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pirn.domains.data.quality_check import QualityCheck


@dataclass(frozen=True)
class QualityReport:
    """Result of a quality knot.

    ``passed`` must be ``False`` whenever any contained
    :class:`QualityCheck` failed — the invariant is enforced in
    :meth:`__post_init__`.
    """

    passed: bool
    checks: tuple[QualityCheck, ...] = ()
    row_count: int = 0
    sampled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if any(not c.passed for c in self.checks) and self.passed:
            raise ValueError("QualityReport.passed cannot be True when any check failed")

    @property
    def failed_checks(self) -> tuple[QualityCheck, ...]:
        return tuple(c for c in self.checks if not c.passed)
