"""``MemorySearchRetriever`` — top-k similarity search over a :class:`MemoryStore`.

Wraps :meth:`MemoryStore.search` (which yields an
``AsyncIterator[Mapping[str, Any]]``) into a single eager ``list`` of
hits suitable for downstream context-injection knots in RAG pipelines.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.agents.memory_store import MemoryStore


class MemorySearchRetriever(Knot):
    """Searches a :class:`MemoryStore` and materialises ``top_k`` hits."""

    def __init__(
        self,
        *,
        store: MemoryStore,
        query: Knot | str,
        _config: KnotConfig,
        top_k: int = 5,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, MemoryStore):
            raise TypeError(
                "MemorySearchRetriever: store must be a MemoryStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(
                "MemorySearchRetriever: top_k must be a positive int, "
                f"got {top_k!r}"
            )
        super().__init__(
            store=store,
            query=query,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        store: MemoryStore,
        query: str,
        top_k: int,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Search the memory store for top_k entries matching the query and return them as a list.

        Args:
            store: The MemoryStore to search against.
            query: The query string used for similarity search.
            top_k: The maximum number of results to return.

        Returns:
            A list of up to top_k matching memory entries as Mapping objects.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(
                "MemorySearchRetriever: query must be a string, "
                f"got {type(query).__name__}"
            )
        candidate = store.search(query, top_k=top_k)
        if hasattr(candidate, "__await__"):
            candidate = await candidate  # type: ignore[assignment]
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
