"""``MemorySearchRetriever`` — top-k similarity search over a :class:`MemoryStore`.

Wraps :meth:`MemoryStore.search` (a single ``await`` away from a concrete
``Sequence[Mapping[str, Any]]``, per its contract) into a plain ``list`` of
hits suitable for downstream context-injection knots in RAG pipelines.

Algorithm:
    1. Validate ``store``, ``top_k``, and ``query`` types.
    2. ``await store.search(query, top_k=top_k)``.
    3. Return the result as a ``list[Mapping[str, Any]]``, sliced to
       ``top_k`` in case a store returns more than asked.

References:
    - pirn-native implementation; no external algorithm reference.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.stores.memory_store import MemoryStore


class MemorySearchRetriever(Retriever):
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
            ValueError: If top_k is not a positive int.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"MemorySearchRetriever: top_k must be a positive int, got {top_k!r}")
        hits = await store.search(query, top_k=top_k)
        return list(hits[:top_k])
