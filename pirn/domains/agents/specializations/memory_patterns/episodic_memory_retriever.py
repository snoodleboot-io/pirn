"""``EpisodicMemoryRetriever`` — retrieve episodic memories from a :class:`MemoryStore`.

Queries the store for episodic memories relevant to the current context
and returns the matching memory entries as a list.
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
        store: MemoryStore,
        _config: KnotConfig,
        top_k: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "EpisodicMemoryRetriever: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "EpisodicMemoryRetriever: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        self._store = store
        self._top_k = top_k
        super().__init__(context=context, _config=_config, **kwargs)

    async def process(
        self,
        context: str,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Query the memory store for episodic memories relevant to context.

        Args:
            context: The current context string used as the search query.

        Returns:
            A list of matching memory entry Mappings up to top_k results.

        Raises:
            TypeError: If context is not a string.
        """
        if not isinstance(context, str):
            raise TypeError(
                "EpisodicMemoryRetriever: context must be a string, "
                f"got {type(context).__name__}"
            )
        candidate = self._store.search(context, top_k=self._top_k)
        if hasattr(candidate, "__await__"):
            candidate = await candidate
        if hasattr(candidate, "__aiter__"):
            collected: list[Mapping[str, Any]] = []
            async for item in candidate:
                collected.append(item)
                if len(collected) >= self._top_k:
                    break
            return collected
        if isinstance(candidate, list):
            return list(candidate[: self._top_k])
        return [item for item in candidate][: self._top_k]
