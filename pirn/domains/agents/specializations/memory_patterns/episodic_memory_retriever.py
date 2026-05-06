"""``EpisodicMemoryRetriever`` — retrieve episodic memories from a :class:`MemoryStore`.

Queries the store for episodic memories relevant to the current context
and returns the matching memory entries as a list.

Algorithm
---------
1. Validate inputs.
2. Call ``store.search(context, top_k=top_k)`` which may be sync,
   async, or an async-iterable.
3. Collect up to ``top_k`` results and return them.

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
from pirn.domains.agents.memory_store import MemoryStore


class EpisodicMemoryRetriever(Knot):
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
            TypeError: If context is not a string or store is not a MemoryStore.
            ValueError: If top_k is not a positive int.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"EpisodicMemoryRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                f"EpisodicMemoryRetriever: top_k must be a positive int, got {top_k!r}"
            )
        if not isinstance(context, str):
            raise TypeError(
                f"EpisodicMemoryRetriever: context must be a string, got {type(context).__name__}"
            )
        candidate = store.search(context, top_k=top_k)
        if hasattr(candidate, "__await__"):
            candidate = await candidate
        if hasattr(candidate, "__aiter__"):
            collected: list[Mapping[str, Any]] = []
            async for item in candidate:
                collected.append(item)
                if len(collected) >= top_k:
                    break
            return collected
        if isinstance(candidate, list):
            return list(candidate[:top_k])
        return [item for item in candidate][:top_k]
