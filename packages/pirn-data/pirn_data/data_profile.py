"""``DataProfile`` — descriptive statistics for a :class:`DataBatch`.

Emitted by :class:`pirn_data.quality.profiler.Profiler`. A profile
is observation, not policy: every field describes the input batch, no
field carries a pass/fail verdict. Compose with a downstream knot if you
want thresholds enforced (or use :class:`NullRateCheck` /
:class:`RowCountCheck` directly). Per-column statistics live in
:class:`pirn_data.column_profile.ColumnProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from pirn_data.column_profile import ColumnProfile


@dataclass(frozen=True)
class DataProfile:
    """Aggregate profile of a :class:`DataBatch`."""

    row_count: int
    column_count: int
    columns: tuple[ColumnProfile, ...] = ()
    sampled_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def column(self, name: str) -> ColumnProfile | None:
        """Return the per-column profile for ``name`` or ``None``."""
        for c in self.columns:
            if c.name == name:
                return c
        return None
