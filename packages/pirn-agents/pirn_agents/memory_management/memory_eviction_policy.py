"""``MemoryEvictionPolicy`` — decide which stored memories to forget.

Eviction bounds store growth so search stays fast. A policy inspects a batch of
:class:`~pirn_agents.memory_management.memory_record.MemoryRecord` (the candidate
set the caller lists out of the store — the
:class:`~pirn_agents.memory_store.MemoryStore` interface itself is left unchanged)
and returns the subset to forget. Concrete policies override only
:meth:`select`: TTL-based expiry, low-value decay eviction, or a composite. This
mirrors the context-layer ``EvictionPolicy`` seam but operates over durable
memory records and time rather than a token budget.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_record import MemoryRecord


class MemoryEvictionPolicy(PirnOpaqueValue):
    """Interface for selecting memory records to evict from a store."""

    def select(
        self,
        records: Sequence[MemoryRecord],
        *,
        now: datetime,
        capacity: int | None = None,
    ) -> tuple[MemoryRecord, ...]:
        """Return the records that should be evicted.

        Args:
            records: The candidate records currently held.
            now: The timezone-aware reference time.
            capacity: Optional maximum records to retain; policies that do not
                bound by count may ignore it.

        Returns:
            The subset of ``records`` to forget, as an immutable tuple.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement select()")
