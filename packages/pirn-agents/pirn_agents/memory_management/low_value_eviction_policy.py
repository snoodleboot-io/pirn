"""``LowValueEvictionPolicy`` — keep the top-``capacity`` most valuable memories.

When the store exceeds a capacity budget this policy evicts the lowest-value
records first, where value is the shared importance x recency
:func:`~pirn_agents.memory_management.decay_function.decay_score` (the same signal
:class:`~pirn_agents.memory_management.decay_scorer.DecayScorer` exposes). Records
are ranked by decayed value at ``now``; everything below the top ``capacity`` is
selected for eviction. Ties break deterministically by record ``id`` so eviction
is reproducible. With no ``capacity`` the policy evicts nothing — capacity is what
bounds growth here.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pirn_agents.memory_management.decay_function import decay_score
from pirn_agents.memory_management.memory_eviction_policy import MemoryEvictionPolicy
from pirn_agents.memory_management.memory_record import MemoryRecord


class LowValueEvictionPolicy(MemoryEvictionPolicy):
    """Evicts the lowest-value records once a capacity budget is exceeded."""

    def __init__(self, *, half_life_seconds: float = 86400.0) -> None:
        """Create the policy.

        Args:
            half_life_seconds: Recency half-life used when scoring value; must be
                positive.

        Raises:
            ValueError: If ``half_life_seconds`` is not positive.
        """
        if not isinstance(half_life_seconds, (int, float)) or isinstance(half_life_seconds, bool):
            raise TypeError("LowValueEvictionPolicy: half_life_seconds must be a real number")
        if half_life_seconds <= 0:
            raise ValueError("LowValueEvictionPolicy: half_life_seconds must be positive")
        self._half_life_seconds = float(half_life_seconds)

    def select(
        self,
        records: Sequence[MemoryRecord],
        *,
        now: datetime,
        capacity: int | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """Return the lowest-value records beyond ``capacity``.

        Args:
            records: The candidate records.
            now: The timezone-aware reference time.
            capacity: Maximum records to retain; ``None`` evicts nothing.

        Returns:
            The evicted records (lowest value first).

        Raises:
            TypeError: If ``now`` is not a datetime or an element is not a record.
            ValueError: If ``capacity`` is negative.
        """
        if not isinstance(now, datetime):
            raise TypeError(
                f"LowValueEvictionPolicy: now must be a datetime, got {type(now).__name__}"
            )
        candidates = tuple(self._require_record(record) for record in records)
        if capacity is None:
            return ()
        if capacity < 0:
            raise ValueError(f"LowValueEvictionPolicy: capacity must be >= 0, got {capacity!r}")
        if len(candidates) <= capacity:
            return ()
        ranked = sorted(candidates, key=lambda record: (self._value(record, now), record.id))
        evict_count = len(candidates) - capacity
        return tuple(ranked[:evict_count])

    @staticmethod
    def _require_record(record: MemoryRecord) -> MemoryRecord:
        """Return ``record`` after asserting it is a :class:`MemoryRecord`."""
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"LowValueEvictionPolicy: every record must be a MemoryRecord, "
                f"got {type(record).__name__}"
            )
        return record

    def _value(self, record: MemoryRecord, now: datetime) -> float:
        """Return ``record``'s decayed value at ``now``."""
        age_seconds = (now - record.recency_anchor()).total_seconds()
        return decay_score(record.importance, age_seconds, self._half_life_seconds)
