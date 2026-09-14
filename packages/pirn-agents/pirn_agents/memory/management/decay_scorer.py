"""``DecayScorer`` — score a memory record's current importance x recency value.

The S2 scoring knot. Given a record and the current time it returns the record's
decayed value via the shared
:meth:`~pirn_agents.memory.management.decay_function.DecayFunction.score` primitive,
measuring age from the record's recency anchor (``last_accessed`` when set, else
``created_at``). The half-life is a construction-time config, so the same knot
expresses fast-forgetting working memory (short half-life) or durable semantic
memory (long half-life). The score feeds eviction and ranked recall.

Math:
    Given the record's ``importance`` in :math:`[0, 1]`, its age at ``now`` in
    seconds, and the configured ``half_life_seconds`` (must be positive):

    $$
    \\text{value} = \\text{importance} \\cdot 2^{-\\,\\text{age\\_seconds} / \\text{half\\_life\\_seconds}}
    $$

    A record at age zero keeps its full importance; after one half-life its
    value halves, and so on. A negative age (a recency anchor in the future,
    e.g. clock skew) is not separately clamped here — see
    :meth:`~pirn_agents.memory.management.decay_function.DecayFunction.score` for the
    shared primitive's own edge-case handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.management.decay_function import DecayFunction
from pirn_agents.memory.management.memory_record import MemoryRecord


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
            ValueError: If ``half_life_seconds`` is not positive.
        """
        age_seconds = (now - record.recency_anchor()).total_seconds()
        return DecayFunction.score(record.metadata.importance, age_seconds, half_life_seconds)
