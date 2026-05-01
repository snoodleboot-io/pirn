"""``DataProfile`` and ``ColumnProfile`` — descriptive statistics for a
:class:`DataBatch`.

Emitted by :class:`pirn.domains.data.quality.profiler.Profiler`. A profile
is observation, not policy: every field describes the input batch, no
field carries a pass/fail verdict. Compose with a downstream knot if you
want thresholds enforced (or use :class:`NullRateGate` /
:class:`RowCountGate` directly).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class ColumnProfile:
    """Per-column statistics."""

    name: str
    observed_count: int
    null_count: int
    distinct_count: int
    min_value: Any | None = None
    max_value: Any | None = None
    top_value: Any | None = None
    top_value_count: int = 0


@dataclass(frozen=True)
class DataProfile:
    """Aggregate profile of a :class:`DataBatch`."""

    row_count: int
    column_count: int
    columns: tuple[ColumnProfile, ...] = ()
    sampled_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def column(self, name: str) -> ColumnProfile | None:
        """Return the per-column profile for ``name`` or ``None``."""
        for c in self.columns:
            if c.name == name:
                return c
        return None
