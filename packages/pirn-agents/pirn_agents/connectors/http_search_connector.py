"""``HttpSearchConnector`` — a generic HTTP search-API adapter (F16-S3 / PIR-358).

The provider-neutral search interface is
:class:`~pirn_agents.tools.web.search_backend.SearchBackend` (an injected
backend the :class:`~pirn_agents.tools.web.web_search_tool.WebSearchTool`
already consumes through the *interface*, never a concrete class). This module
ships **one** reference adapter over that interface: a generic JSON HTTP search
API driven by the pooled :class:`~pirn_agents.connectors.http_connector.HttpConnector`.

No vendor is hard-wired: the request query-parameter name and the JSON keys for
the results array and each result's title/url/snippet are all configuration, so
the same adapter targets any search API returning JSON. The backend (``httpx``)
stays lazy because it is only touched through the pooled ``HttpConnector``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pirn_agents.connectors.http_connector import HttpConnector
from pirn_agents.tools.web.search_backend import SearchBackend


class HttpSearchConnector(SearchBackend):
    """Provider-neutral :class:`SearchBackend` over a generic JSON HTTP search API."""

    def __init__(
        self,
        *,
        http: HttpConnector,
        endpoint: str,
        query_param: str = "q",
        results_key: str = "results",
        title_key: str = "title",
        url_key: str = "url",
        snippet_key: str = "snippet",
        extra_params: Mapping[str, Any] | None = None,
    ) -> None:
        """Bind the adapter to a pooled HTTP connector and result-shape config.

        Args:
            http: The pooled :class:`HttpConnector` used for every request.
            endpoint: Absolute URL (or ``base_url``-relative path) of the search API.
            query_param: Query-string parameter carrying the search text.
            results_key: JSON key holding the results array (top-level mapping).
            title_key/url_key/snippet_key: Per-result JSON keys to normalise.
            extra_params: Optional fixed query parameters sent with every request.

        Raises:
            TypeError: If ``http`` is not an :class:`HttpConnector`.
            ValueError: If ``endpoint`` is empty.
        """
        if not isinstance(http, HttpConnector):
            raise TypeError(
                f"HttpSearchConnector: http must be an HttpConnector, got {type(http).__name__}"
            )
        if not endpoint:
            raise ValueError("HttpSearchConnector: endpoint must be a non-empty URL")
        self._http = http
        self._endpoint = endpoint
        self._query_param = query_param
        self._results_key = results_key
        self._title_key = title_key
        self._url_key = url_key
        self._snippet_key = snippet_key
        self._extra_params = dict(extra_params or {})

    async def search(self, query: str, *, max_results: int) -> Sequence[Mapping[str, Any]]:
        """Query the HTTP API and return up to ``max_results`` normalised records.

        Returns:
            An ordered sequence of ``{"title", "url", "snippet"}`` mappings.
        """
        params: dict[str, Any] = {self._query_param: query, **self._extra_params}
        response = await self._http.request("GET", self._endpoint, params=params)
        payload = response.json()
        items = payload.get(self._results_key, []) if isinstance(payload, Mapping) else payload
        results: list[dict[str, str]] = []
        for item in list(items)[:max_results]:
            mapping = item if isinstance(item, Mapping) else {}
            results.append(
                {
                    "title": str(mapping.get(self._title_key, "")),
                    "url": str(mapping.get(self._url_key, "")),
                    "snippet": str(mapping.get(self._snippet_key, "")),
                }
            )
        return results

    async def close(self) -> None:
        """Close the underlying pooled HTTP connector (lifecycle teardown)."""
        await self._http.close()
