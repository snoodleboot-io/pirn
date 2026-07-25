"""``TypedMemoryWriter`` — persist a typed record through a plain ``MemoryStore``.

The S5 migration bridge: it serialises a validated
:class:`~pirn_agents.memory_management.memory_record.MemoryRecord` with
:meth:`MemoryRecord.to_payload` and writes the resulting mapping under the
record's ``id`` via the untyped
:meth:`~pirn_agents.memory_store.MemoryStore.store` interface. Existing
``memory_patterns/`` stores therefore keep reading and writing plain mappings
while producers move to typed+provenance records — no store change required. The
stored key is returned so callers can read the record back and rebuild it with
:meth:`MemoryRecord.from_payload`.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_store import MemoryStore


class TypedMemoryWriter(Knot):
    """Writes one :class:`MemoryRecord` to a :class:`MemoryStore` under its id."""

    def __init__(
        self,
        *,
        record: Knot | MemoryRecord,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(record=record, store=store, _config=_config, **kwargs)

    async def process(
        self,
        record: MemoryRecord,
        store: MemoryStore,
        **_: Any,
    ) -> str:
        """Persist ``record`` as a payload mapping and return its storage key.

        Args:
            record: The typed record to persist.
            store: The MemoryStore to write into.

        Returns:
            The key (the record ``id``) under which the payload was stored.

        Raises:
            TypeError: If ``record`` is not a MemoryRecord or ``store`` is not a
                MemoryStore.
        """
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"TypedMemoryWriter: record must be a MemoryRecord, got {type(record).__name__}"
            )
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"TypedMemoryWriter: store must be a MemoryStore, got {type(store).__name__}"
            )
        await store.store(record.id, record.to_payload())
        return record.id
