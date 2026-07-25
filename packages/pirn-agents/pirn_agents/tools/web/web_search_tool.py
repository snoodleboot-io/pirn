"""``WebSearchTool`` — pluggable web search via an injected :class:`SearchBackend`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn_agents.tools.base_tool import BaseTool
from pirn_agents.tools.web.search_backend import SearchBackend


class WebSearchTool(BaseTool):
    """Search the web through a user-supplied, vendor-neutral search backend."""

    def __init__(
        self,
        *,
        backend: SearchBackend,
        max_results: int = 5,
        snippet_chars: int = 400,
    ) -> None:
        """Bind the tool to a search backend and output caps.

        Args:
            backend: The injected :class:`SearchBackend` performing the search.
            max_results: Default and hard ceiling on returned results.
            snippet_chars: Maximum characters kept per result snippet.

        Raises:
            TypeError: If ``backend`` is not a :class:`SearchBackend`.
            ValueError: If ``max_results`` or ``snippet_chars`` is not positive.
        """
        if not isinstance(backend, SearchBackend):
            raise TypeError(
                f"web_search: backend must be a SearchBackend, got {type(backend).__name__}"
            )
        if max_results <= 0:
            raise ValueError(f"web_search: max_results must be positive, got {max_results}")
        if snippet_chars <= 0:
            raise ValueError(f"web_search: snippet_chars must be positive, got {snippet_chars}")
        self._backend = backend
        self._max_results = max_results
        self._snippet_chars = snippet_chars

    @property
    def name(self) -> str:
        """Return the stable tool identifier ``"web_search"``."""
        return "web_search"

    @property
    def description(self) -> str:
        """Return the human-readable description shown to the planner."""
        return "Search the web for a query and return ranked {title, url, snippet} results."

    @property
    def parameters_schema(self) -> Mapping[str, Any]:
        """Return the JSON Schema for the ``query`` and optional ``max_results``."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The search query."},
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return.",
                },
            },
            "required": ["query"],
        }

    async def invoke(self, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        """Run the query through the backend and return normalised results.

        Returns:
            ``{"query", "results": [{"title", "url", "snippet"}...], "count"}``.

        Raises:
            TypeError: If ``arguments`` is not a mapping.
            ValueError: If ``query`` is missing/empty.
        """
        self._require_mapping(self.name, arguments)
        query = self._string_argument(self.name, arguments, "query")
        requested = arguments.get("max_results")
        limit = requested if isinstance(requested, int) and requested > 0 else self._max_results
        limit = min(limit, self._max_results)
        raw = await self._backend.search(query, max_results=limit)
        results = [self._normalise(item) for item in list(raw)[:limit]]
        return {"query": query, "results": results, "count": len(results)}

    def _normalise(self, item: Mapping[str, Any]) -> dict[str, str]:
        """Coerce a backend result mapping to a ``{title, url, snippet}`` record."""
        snippet = str(item.get("snippet", ""))[: self._snippet_chars]
        return {
            "title": str(item.get("title", "")),
            "url": str(item.get("url", "")),
            "snippet": snippet,
        }
