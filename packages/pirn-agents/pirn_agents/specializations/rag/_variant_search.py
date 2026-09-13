"""``_VariantSearch`` — search the store for one query variant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class _VariantSearch(Knot):
    """Search the store for one query variant and return its ranked hits."""

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | MemoryStore,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, store=store, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        query: str,
        store: MemoryStore,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Search ``store`` for ``query`` and return up to ``top_k`` hits.

        Args:
            query: The query variant to search for.
            store: The memory store to search.
            top_k: Maximum number of hits to fetch.

        Returns:
            The hits for this query variant, in ranked order.
        """
        return [item async for item in await store.search(query, top_k=top_k)]
