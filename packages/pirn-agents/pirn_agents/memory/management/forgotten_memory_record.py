"""``ForgottenMemoryRecord`` — evict one record from a store, as its own knot.

Per-victim knot of
:class:`~pirn_agents.memory.management.memory_evictor.MemoryEvictor`. The
records an eviction policy selects are independent of one another, so the
evictor runs one ``ForgottenMemoryRecord`` per victim inside a nested run
(:class:`~pirn.nodes.nested_run_knot.NestedRunKnot`) joined by an
:class:`~pirn.nodes.aggregator.Aggregator`: every ``forget`` gets its own
lineage row, ``Result`` and admission slot, so a single failing eviction is
attributable and the batch runs concurrently under the enclosing run's caps
instead of one ``await`` at a time inside a single ``process()`` (PIR-873).

Algorithm:
    1. Call ``store.forget(record_id)``.
    2. Return the id, so the evictor can report what it dropped in policy order.

Internal API.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class ForgottenMemoryRecord(Knot):
    """Forget one record id from a :class:`MemoryStore` and return that id."""

    def __init__(
        self,
        *,
        record_id: Knot | str,
        store: Knot | MemoryStore,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(record_id=record_id, store=store, _config=_config, **kwargs)

    async def process(self, record_id: str, store: MemoryStore, **_: Any) -> str:
        """Forget ``record_id`` and return it.

        Args:
            record_id: The id of the record to drop.
            store: The store to forget it from.

        Returns:
            ``record_id``.

        Raises:
            ValueError: If ``record_id`` is empty.
        """
        if not record_id:
            raise ValueError("ForgottenMemoryRecord: record_id must be a non-empty string")
        await store.forget(record_id)
        return record_id
