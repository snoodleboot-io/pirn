"""Async ``ApiClient`` wrapper around the Prometheus HTTP query API.

Prometheus exposes a JSON HTTP API at ``/api/v1/query``,
``/api/v1/query_range``, ``/api/v1/series``, etc. The official
``prometheus-client`` Python package is for *exposing* metrics from a
Python process — it is not a query client. For querying we use
:mod:`httpx` directly (installed via the ``pirn[http]`` extra and shared
with the rest of pirn's HTTP plumbing).

The connector implements :class:`MetricQuery`. ``query`` routes to the
instant endpoint when ``start`` is omitted and to the range endpoint
otherwise. Vendor-typed :meth:`query_instant` and :meth:`query_range`
expose the raw shape directly.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.capabilities.metric_query import MetricQuery
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.observability.prometheus_config import (
    PrometheusConfig,
)


class PrometheusClient(ApiClient, MetricQuery):
    """Concrete :class:`ApiClient` for the Prometheus HTTP query API."""

    def __init__(
        self,
        config: PrometheusConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("PrometheusClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> PrometheusConfig | None:
        return self._config

    async def query(
        self,
        query: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> Mapping[str, Any]:
        """:class:`MetricQuery` adapter — picks instant vs range.

        - Instant query (``/api/v1/query``) when ``start`` is None.
        - Range query (``/api/v1/query_range``) when ``start`` is set;
          ``end`` defaults to ``start`` if omitted, and ``step``
          defaults to ``"60s"``.
        """
        if not isinstance(query, str) or not query:
            raise ValueError("PrometheusClient.query: query must be non-empty")
        if start is None:
            return await self.query_instant(query, time=end)
        if end is None:
            raise ValueError("PrometheusClient.query: end is required when start is set")
        return await self.query_range(query, start=start, end=end, step=step or "60s")

    async def query_instant(
        self,
        query: str,
        *,
        time: datetime | None = None,
    ) -> Mapping[str, Any]:
        """Vendor-typed instant query against ``/api/v1/query``."""
        if not isinstance(query, str) or not query:
            raise ValueError("PrometheusClient.query_instant: query must be non-empty")
        params: dict[str, Any] = {"query": query}
        if time is not None:
            params["time"] = int(time.timestamp())
        response = await self.request("GET", "/api/v1/query", params=params)
        if not isinstance(response, Mapping):
            return {"data": response}
        return response

    async def query_range(
        self,
        query: str,
        *,
        start: datetime,
        end: datetime,
        step: str = "60s",
    ) -> Mapping[str, Any]:
        """Vendor-typed range query against ``/api/v1/query_range``."""
        if not isinstance(query, str) or not query:
            raise ValueError("PrometheusClient.query_range: query must be non-empty")
        if not isinstance(step, str) or not step:
            raise ValueError("PrometheusClient.query_range: step must be non-empty")
        params = {
            "query": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "step": step,
        }
        response = await self.request("GET", "/api/v1/query_range", params=params)
        if not isinstance(response, Mapping):
            return {"data": response}
        return response

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        if not isinstance(method, str) or not method:
            raise ValueError("PrometheusClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("PrometheusClient.request: path must be non-empty")
        client = await self._ensure_client()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        try:
            response = await client.request(
                method.upper(),
                path,
                params=request_params,
                json=request_body,
                headers=request_headers,
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        return response.json()

    async def close(self) -> None:
        if self._client is not None:
            aclose = getattr(self._client, "aclose", None)
            if callable(aclose):
                await aclose()  # type: ignore[misc]
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("prometheus.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("PrometheusClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "PrometheusClient requires httpx; install via `pip install pirn[http]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("PrometheusClient: missing config and no injected client")
        if self._config.base_url is None:
            raise RuntimeError("PrometheusClient: config.base_url is required")

        client_headers: dict[str, str] = {}
        if self._config.bearer_token is not None:
            client_headers["Authorization"] = f"Bearer {self._config.bearer_token}"

        try:
            client = httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/"),
                headers=client_headers or None,
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("prometheus.connect")
        return client
