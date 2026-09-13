"""``_RetrievalRound`` — search the store for the current round's query."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.stores.memory_store import MemoryStore


class _RetrievalRound(Knot):
    """Search the store for the current round's query."""

    def __init__(
        self,
        *,
        memory: Knot | MemoryStore,
        query: Knot | str,
        top_k: Knot | int,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(memory=memory, query=query, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        memory: MemoryStore,
        query: str,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Search ``memory`` for ``query`` and return up to ``top_k`` hits.

        Args:
            memory: The memory store to search.
            query: The current round's query.
            top_k: Maximum number of hits to fetch.

        Returns:
            The hits for this round.
        """
        return [item async for item in await memory.search(query, top_k=top_k)]
