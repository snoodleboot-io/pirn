"""``WebSearchTool`` — pluggable web search via a bound :class:`SearchBackend`."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pydantic import Field

from pirn_agents.tools.tool import Tool
from pirn_agents.tools.web.search_backend import SearchBackend


class WebSearchTool(Tool):
    """Search the web for a query and return ranked {title, url, snippet} results."""

    tool_name: ClassVar[str] = "web_search"

    def __init__(
        self,
        *,
        query: Knot | str,
        backend: Knot | SearchBackend,
        max_results: Knot | int = 5,
        result_ceiling: Knot | int = 5,
        snippet_chars: Knot | int = 400,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            query=query,
            backend=backend,
            max_results=max_results,
            result_ceiling=result_ceiling,
            snippet_chars=snippet_chars,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        query: Annotated[str, Field(description="The search query.")],
        backend: SearchBackend,
        max_results: Annotated[int, Field(description="Maximum number of results to return.")] = 5,
        result_ceiling: int = 5,
        snippet_chars: int = 400,
        **_: Any,
    ) -> Mapping[str, Any]:
        """Run the query through the backend and return normalised results.

        Args:
            query: The search query.
            backend: The vendor-neutral :class:`SearchBackend`; bound once with
                ``WebSearchTool.bind(backend=...)``.
            max_results: Number of results the caller asks for.
            result_ceiling: Hard ceiling on returned results, bound by the
                pipeline author; a request above it is capped, never refused.
            snippet_chars: Maximum characters kept per result snippet.

        Returns:
            ``{"query", "results": [{"title", "url", "snippet"}...], "count"}``.

        Raises:
            ValueError: If ``query`` is empty or a bound cap is not positive.
        """
        if not query:
            raise ValueError("web_search: 'query' must be a non-empty string")
        if result_ceiling <= 0:
            raise ValueError(f"web_search: result_ceiling must be positive, got {result_ceiling}")
        if snippet_chars <= 0:
            raise ValueError(f"web_search: snippet_chars must be positive, got {snippet_chars}")
        requested = max_results if max_results > 0 else result_ceiling
        limit = min(requested, result_ceiling)
        raw = await backend.search(query, max_results=limit)
        results = [self._normalise(item, snippet_chars) for item in list(raw)[:limit]]
        return {"query": query, "results": results, "count": len(results)}

    @staticmethod
    def _normalise(item: Mapping[str, Any], snippet_chars: int) -> dict[str, str]:
        """Coerce a backend result mapping to a ``{title, url, snippet}`` record."""
        snippet = str(item.get("snippet", ""))[:snippet_chars]
        return {
            "title": str(item.get("title", "")),
            "url": str(item.get("url", "")),
            "snippet": snippet,
        }
