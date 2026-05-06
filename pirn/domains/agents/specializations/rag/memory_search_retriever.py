"""``MemorySearchRetriever`` — top-k similarity search over a :class:`MemoryStore`.

Wraps :meth:`MemoryStore.search` (which yields an
``AsyncIterator[Mapping[str, Any]]``) into a single eager ``list`` of
hits suitable for downstream context-injection knots in RAG pipelines.

Algorithm:
    1. Validate ``store``, ``top_k``, and ``query`` types.
    2. Call ``store.search(query, top_k=top_k)``; the return type may
       be an awaitable, an async iterable, or a plain list.
    3. Await the result if it is an awaitable.
    4. Drain up to ``top_k`` items if the result is an async iterable.
    5. Slice to ``top_k`` if the result is a plain list.
    6. Return the collected items as a ``list[Mapping[str, Any]]``.

References:
    - pirn-native implementation; no external algorithm reference.
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
        store: Knot | MemoryStore,
        query: Knot | str,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
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
            TypeError: If store is not a MemoryStore or query is not a string.
            ValueError: If top_k is not a positive int.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemorySearchRetriever: store must be a MemoryStore, got {type(store).__name__}"
            )
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"MemorySearchRetriever: top_k must be a positive int, got {top_k!r}")
        if not isinstance(query, str):
            raise TypeError(
                f"MemorySearchRetriever: query must be a string, got {type(query).__name__}"
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
