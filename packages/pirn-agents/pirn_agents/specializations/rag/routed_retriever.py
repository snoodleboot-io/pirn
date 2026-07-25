"""``RoutedRetriever`` — retrieve from the store a classifier selected.

The dispatch stage of Router RAG. Given a chosen ``route`` name and the
:class:`RouteTable` of candidate stores, it searches only the selected store and
returns the hits, tagged with the route that produced them.

Algorithm:
    1. Validate ``route`` (str), ``routes`` (:class:`RouteTable`), ``query``
       (str), and ``top_k`` (positive int).
    2. Look the route up in the table (falling back to the first route when the
       name is unknown, so a misrouted classification still returns context).
    3. Search the selected store for ``top_k`` hits and tag each with ``route``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.specializations.rag.route_table import RouteTable


class RoutedRetriever(Knot):
    """Retrieve from the single store named by ``route`` in a :class:`RouteTable`."""

    def __init__(
        self,
        *,
        route: Knot | str,
        routes: Knot | RouteTable,
        query: Knot | str,
        _config: KnotConfig,
        top_k: Knot | int = 5,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            route=route,
            routes=routes,
            query=query,
            top_k=top_k,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        route: str,
        routes: RouteTable,
        query: str,
        top_k: int = 5,
        **_: Any,
    ) -> list[Mapping[str, Any]]:
        """Retrieve ``top_k`` hits from the store named by ``route``.

        Args:
            route: The route name chosen by the classifier.
            routes: The table of candidate stores.
            query: The query searched against the selected store.
            top_k: Number of hits to return.

        Returns:
            The retrieved documents, each tagged with a ``route`` key.

        Raises:
            TypeError: If ``routes`` is not a RouteTable or ``query`` is not a string.
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(routes, RouteTable):
            raise TypeError(
                f"RoutedRetriever: routes must be a RouteTable, got {type(routes).__name__}"
            )
        if not isinstance(query, str):
            raise TypeError(f"RoutedRetriever: query must be a string, got {type(query).__name__}")
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"RoutedRetriever: top_k must be a positive int, got {top_k!r}")
        selected = route if routes.has(route) else routes.route_names()[0]
        store = routes.store_for(selected)
        hits = await self._search(store, query, top_k)
        tagged: list[Mapping[str, Any]] = []
        for hit in hits:
            enriched = dict(hit)
            enriched.setdefault("route", selected)
            tagged.append(enriched)
        return tagged

    @staticmethod
    async def _search(store: Any, query: str, top_k: int) -> list[Mapping[str, Any]]:
        """Drain ``store.search`` (awaitable / async-iterable / list) into a list."""
        candidate = store.search(query, top_k=top_k)
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
