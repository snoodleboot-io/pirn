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

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.specializations.rag.route_table import RouteTable


class RoutedRetriever(Retriever):
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
            ValueError: If ``top_k`` is not a positive integer.
        """
        if not isinstance(top_k, int) or top_k <= 0:
            raise ValueError(f"RoutedRetriever: top_k must be a positive int, got {top_k!r}")
        selected = route if routes.has(route) else routes.route_names()[0]
        store = routes.store_for(selected)
        hits = await store.search(query, top_k=top_k)
        tagged: list[Mapping[str, Any]] = []
        for hit in list(hits)[:top_k]:
            enriched = dict(hit)
            enriched.setdefault("route", selected)
            tagged.append(enriched)
        return tagged
