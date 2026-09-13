"""``EpisodicMemoryRetriever`` — retrieve episodic memories from a :class:`MemoryStore`.

Queries the store for episodic memories relevant to the current context
and returns the matching memory entries as a list.

Algorithm
---------
1. Validate inputs.
2. ``await store.search(context, top_k=top_k)``.
3. Return up to ``top_k`` results as a list.

Math
----
No mathematical operations.

References
----------
None.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore


class EpisodicMemoryRetriever(Retriever):
    """Search a :class:`MemoryStore` for episodic memories matching a context query."""

    def __init__(
        self,
        *,
        context: Knot | str,
        store: Knot | MemoryStore,
        top_k: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(context=context, store=store, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        context: str,
        store: MemoryStore,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Query the memory store for episodic memories relevant to context.

        Args:
            context: The current context string used as the search query.
            store: The MemoryStore to search.
            top_k: Maximum number of results to return.

        Returns:
            A list of matching memory entry Mappings up to top_k results.

        Raises:
            ValueError: If top_k is not a positive int.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                f"EpisodicMemoryRetriever: top_k must be a positive int, got {top_k!r}"
            )
        hits = await store.search(context, top_k=top_k)
        return list(hits[:top_k])
