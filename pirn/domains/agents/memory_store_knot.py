"""``MemoryStoreKnot`` — vending Knot for a :class:`MemoryStore`.

Wraps an externally-constructed store so it participates in the pirn graph
with full lineage. Consumers receive the resolved store value in their
``process()`` calls.

Algorithm:
    1. Accept the store value (resolved by the framework from an upstream
       Knot or a scalar passed at pipeline-build time).
    2. Return it unchanged so downstream Knots receive the store instance.


References:
    - :class:`pirn.domains.agents.memory_store.MemoryStore`
"""
from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore


class MemoryStoreKnot(Knot):
    """Vending Knot that passes a :class:`MemoryStore` through the graph."""

    def __init__(self, *, store: Knot | MemoryStore, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(store=store, _config=_config, **kwargs)

    async def process(self, store: MemoryStore, **_: Any) -> MemoryStore:
        """Return the store unchanged.

        Args:
            store: The memory store instance to pass through.

        Returns:
            The store instance unchanged.
        """
        return store
