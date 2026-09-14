"""``ColumnProfile`` — per-column statistics inside a :class:`DataProfile`.

Emitted by :class:`pirn_data.quality.profiler.Profiler` as one entry of
:attr:`pirn_data.data_profile.DataProfile.columns`.
"""

from __future__ import annotations

from dataclasses import dataclass
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
