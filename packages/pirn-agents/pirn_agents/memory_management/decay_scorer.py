"""``DecayScorer`` — score a memory record's current importance x recency value.

The S2 scoring knot. Given a record and the current time it returns the record's
decayed value via the shared
:func:`~pirn_agents.memory_management.decay_function.decay_score` primitive,
measuring age from the record's recency anchor (``last_accessed`` when set, else
``created_at``). The half-life is a construction-time config, so the same knot
expresses fast-forgetting working memory (short half-life) or durable semantic
memory (long half-life). The score feeds eviction and ranked recall.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.decay_function import decay_score
from pirn_agents.memory_management.memory_record import MemoryRecord


class DecayScorer(Knot):
    """Computes a record's half-life-decayed importance value at a given time."""

    def __init__(
        self,
        *,
        record: Knot | MemoryRecord,
        now: Knot | datetime,
        half_life_seconds: Knot | float = 86400.0,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            record=record,
            now=now,
            half_life_seconds=half_life_seconds,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        record: MemoryRecord,
        now: datetime,
        half_life_seconds: float = 86400.0,
        **_: Any,
    ) -> float:
        """Return ``record``'s decayed value as of ``now``.

        Args:
            record: The record to score.
            now: The timezone-aware reference time.
            half_life_seconds: Recency half-life in seconds; must be positive.

        Returns:
            The decayed value ``importance * 2 ** (-age / half_life)``.

        Raises:
            TypeError: If ``record`` is not a MemoryRecord or ``now`` is not a
                datetime.
            ValueError: If ``half_life_seconds`` is not positive.
        """
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"DecayScorer: record must be a MemoryRecord, got {type(record).__name__}"
            )
        if not isinstance(now, datetime):
            raise TypeError(f"DecayScorer: now must be a datetime, got {type(now).__name__}")
        age_seconds = (now - record.recency_anchor()).total_seconds()
        return decay_score(record.importance, age_seconds, half_life_seconds)
