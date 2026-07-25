"""``TtlEvictionPolicy`` — evict memories older than a fixed time-to-live.

The simplest S2 eviction rule: any record whose age at ``now`` — measured from its
recency anchor (``last_accessed`` when set, else ``created_at``) — exceeds
``ttl_seconds`` is selected for eviction. TTL is orthogonal to F17 compaction:
compaction summarises live context, while this expires stale durable memory, and
the two compose without either touching the
:class:`~pirn_agents.memory_store.MemoryStore` read/write contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pirn_agents.memory_management.memory_eviction_policy import MemoryEvictionPolicy
from pirn_agents.memory_management.memory_record import MemoryRecord


class TtlEvictionPolicy(MemoryEvictionPolicy):
    """Evicts every record older than ``ttl_seconds``."""

    def __init__(self, *, ttl_seconds: float) -> None:
        """Create the policy.

        Args:
            ttl_seconds: Maximum record age in seconds before eviction; must be
                positive.

        Raises:
            ValueError: If ``ttl_seconds`` is not positive.
        """
        if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool):
            raise TypeError("TtlEvictionPolicy: ttl_seconds must be a real number")
        if ttl_seconds <= 0:
            raise ValueError(
                f"TtlEvictionPolicy: ttl_seconds must be positive, got {ttl_seconds!r}"
            )
        self._ttl_seconds = float(ttl_seconds)

    def select(
        self,
        records: Sequence[MemoryRecord],
        *,
        now: datetime,
        capacity: int | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """Return records whose age at ``now`` exceeds the TTL.

        Args:
            records: The candidate records.
            now: The timezone-aware reference time.
            capacity: Ignored; TTL bounds by age, not count.

        Returns:
            The expired records, in input order.

        Raises:
            TypeError: If ``now`` is not a datetime or an element is not a record.
        """
        if not isinstance(now, datetime):
            raise TypeError(f"TtlEvictionPolicy: now must be a datetime, got {type(now).__name__}")
        expired: list[MemoryRecord] = []
        for record in records:
            if not isinstance(record, MemoryRecord):
                raise TypeError(
                    f"TtlEvictionPolicy: every record must be a MemoryRecord, "
                    f"got {type(record).__name__}"
                )
            age_seconds = (now - record.recency_anchor()).total_seconds()
            if age_seconds > self._ttl_seconds:
                expired.append(record)
        return tuple(expired)
