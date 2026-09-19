"""``StoredMemoryRecord`` — persist one :class:`MemoryRecord`, as its own knot.

Per-record knot of
:class:`~pirn_agents.memory.management.memory_consolidator.MemoryConsolidator`.
Writing the consolidated records is one independent store write per record, so
each runs as its own knot downstream of the group that produced it, inside the
consolidator's nested run: every write gets its own lineage row, ``Result`` and
admission slot, and the batch is written concurrently under the enclosing run's
caps instead of one ``await`` at a time inside a single ``process()`` (PIR-873).

Algorithm:
    1. Write ``record.to_payload()`` under ``record.data.id``.
    2. Return the record, so the consolidator's aggregator still sees the
       consolidated records themselves whether or not a store was given.

Internal API.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.stores.memory_store import MemoryStore


class StoredMemoryRecord(Knot):
    """Persist one :class:`MemoryRecord` under its own id and return it unchanged."""

    def __init__(
        self,
        *,
        record: Knot | MemoryRecord,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(record=record, store=store, _config=_config, **kwargs)

    async def process(self, record: MemoryRecord, store: MemoryStore, **_: Any) -> MemoryRecord:
        """Write ``record`` under its id and return it.

        Args:
            record: The record to persist.
            store: The store to write into.

        Returns:
            ``record``, unchanged.
        """
        await store.store(record.data.id, record.to_payload())
        return record
