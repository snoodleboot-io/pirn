"""``RetrieverTool`` — expose a :class:`MemoryStore` similarity search as a tool.

Wraps an injected F4 :class:`~pirn_agents.memory_store.MemoryStore` so an agent
can explicitly decide to retrieve ranked context. Provider-neutral: any store
implementation (vector DB, in-memory, hybrid) works, and nothing vendor-specific
is imported at module load.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.memory_store import MemoryStore
from pirn_agents.tools.base_tool import BaseTool


class RetrieverTool(BaseTool):
    """Retrieve the top-k most similar records for a query from a memory store."""

    def __init__(self, *, store: MemoryStore, top_k: int = 5) -> None:
        """Bind the tool to a memory store and a default result count.

        Args:
            store: The injected :class:`MemoryStore` to search.
            top_k: Default number of ranked results to return.

        Raises:
            TypeError: If ``store`` is not a :class:`MemoryStore`.
            ValueError: If ``top_k`` is not positive.
        """
        if not isinstance(store, MemoryStore):
            raise TypeError(f"retriever: store must be a MemoryStore, got {type(store).__name__}")
        if top_k <= 0:
            raise ValueError(f"retriever: top_k must be positive, got {top_k}")
        self._store: MemoryStore = store
        self._top_k = top_k

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"retriever"``."""
        return "retriever"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Retrieve the most relevant stored records for a query, ranked by similarity."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``query`` and optional ``top_k``."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The retrieval query."},
                "top_k": {
                    "type": "integer",
                    "description": "Number of ranked results to return.",
                },
            },
            "required": ["query"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Search the store and return ranked results.

        Returns:
            ``{"query", "results": [mapping...], "count"}`` — results are ordered
            by the store's ranking.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``query`` is missing/empty.
        """
        self._require_mapping(self.name, arguments)
        query = self._string_argument(self.name, arguments, "query")
        requested = arguments.get("top_k")
        top_k = requested if isinstance(requested, int) and requested > 0 else self._top_k
        results = await self._collect(query, top_k)
        return {"query": query, "results": results, "count": len(results)}

    async def _collect(self, query: str, top_k: int) -> list[dict[str, Any]]:
        """Drain the store's async search iterator into an ordered list."""
        iterator = await self._store.search(query, top_k=top_k)
        collected: list[dict[str, Any]] = []
        async for item in iterator:
            collected.append(dict(item))
            if len(collected) >= top_k:
                break
        return collected

    def _clear_credentials(self) -> None:
        """Drop the store reference so it becomes garbage-collectable."""
        self._store = None  # type: ignore[assignment]
