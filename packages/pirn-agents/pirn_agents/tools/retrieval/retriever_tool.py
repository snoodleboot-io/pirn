"""``RetrieverTool`` — expose a :class:`MemoryStore` similarity search as a tool.

Reads a bound F4 :class:`~pirn_agents.memory.stores.memory_store.MemoryStore` so an agent
can explicitly decide to retrieve ranked context. Provider-neutral: any store
implementation (vector DB, in-memory, hybrid) works, and nothing vendor-specific
is imported at module load.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.memory.stores.memory_store import MemoryStore
from pirn_agents.tools.tool import Tool


class RetrieverTool(Tool):
    """Retrieve the most relevant stored records for a query, ranked by similarity."""

    tool_name: ClassVar[str] = "retriever"

    def __init__(
        self,
        *,
        query: Knot | str,
        store: Knot | MemoryStore,
        top_k: Knot | int = 5,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(query=query, store=store, top_k=top_k, _config=_config, **kwargs)

    async def process(
        self,
        query: Annotated[str, Field(description="The retrieval query.")],
        store: MemoryStore,
        top_k: Annotated[int, Field(description="Number of ranked results to return.")] = 5,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Search the store and return ranked results.

        Args:
            query: The retrieval query.
            store: The :class:`MemoryStore` to search; bound once with
                ``RetrieverTool.bind(store=...)``.
            top_k: Number of ranked results to return.

        Returns:
            ``{"query", "results": [mapping...], "count"}`` — results are ordered
            by the store's ranking.

        Raises:
            ValueError: If ``query`` is empty or ``top_k`` is not positive.
        """
        if not query:
            raise ValueError("retriever: 'query' must be a non-empty string")
        if top_k <= 0:
            raise ValueError(f"retriever: top_k must be positive, got {top_k}")
        hits = await store.search(query, top_k=top_k)
        results = [dict(item) for item in list(hits)[:top_k]]
        return {"query": query, "results": results, "count": len(results)}
