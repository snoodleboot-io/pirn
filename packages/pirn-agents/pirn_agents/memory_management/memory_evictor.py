"""``MemoryEvictor`` — apply an eviction policy and forget the selected records.

The S2 write-side knot. Given the candidate records the caller listed from a
store, an eviction policy, and a store, it asks the policy which records to drop
and calls :meth:`~pirn_agents.memory_store.MemoryStore.forget` for each,
returning the evicted ids. It reads only the batch it is handed and writes only
through ``forget`` — the ``MemoryStore`` read/write contract is untouched, so
eviction composes with F17 compaction and any concrete store backend.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.memory_eviction_policy import MemoryEvictionPolicy
from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_store import MemoryStore


class MemoryEvictor(Knot):
    """Evicts policy-selected records from a :class:`MemoryStore`."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[MemoryRecord],
        policy: Knot | MemoryEvictionPolicy,
        store: Knot | MemoryStore,
        now: Knot | datetime,
        capacity: Knot | int | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            policy=policy,
            store=store,
            now=now,
            capacity=capacity,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[MemoryRecord],
        policy: MemoryEvictionPolicy,
        store: MemoryStore,
        now: datetime,
        capacity: int | None = None,
        **_: Any,
    ) -> tuple[str, ...]:
        """Evict the records ``policy`` selects and return their ids.

        Args:
            records: The candidate records to consider.
            policy: The eviction policy deciding what to drop.
            store: The store to forget evicted records from.
            now: The timezone-aware reference time passed to the policy.
            capacity: Optional retain-count budget forwarded to the policy.

        Returns:
            The ids of the evicted records, in the policy's selection order.

        Raises:
            TypeError: If ``policy`` is not a MemoryEvictionPolicy or ``store`` is
                not a MemoryStore.
        """
        if not isinstance(policy, MemoryEvictionPolicy):
            raise TypeError(
                f"MemoryEvictor: policy must be a MemoryEvictionPolicy, got {type(policy).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryEvictor: store must be a MemoryStore, got {type(store).__name__}"
            )
        victims = policy.select(tuple(records), now=now, capacity=capacity)
        evicted: list[str] = []
        for record in victims:
            if not isinstance(record, MemoryRecord):
                raise TypeError(
                    f"MemoryEvictor: policy returned a non-record {type(record).__name__}"
                )
            await store.forget(record.id)
            evicted.append(record.id)
        return tuple(evicted)
