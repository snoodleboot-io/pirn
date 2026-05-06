"""Async ``ApiClient`` wrapper around the synchronous ``datadog-api-client`` SDK.

The Datadog SDK is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime. The generic :meth:`request` is implemented against the SDK's
low-level ``call_api(method, path, ...)`` so test stubs only need to
expose that single hook (mirrors the SDK's
``datadog_api_client.ApiClient`` shape).

The connector also implements three vendor-neutral capabilities:

1. :class:`TableSource` for paginated reads of metric/event lists.
   ``fetch_page`` is routed at the configured ``resource`` (defaults to
   ``"metrics"``) and uses Datadog's offset/page pagination.
2. :class:`EventEmitter` for ingesting custom metrics through
   ``/api/v1/series``. The event must contain ``metric`` and ``points``
   keys (Datadog's vendor shape).
3. :class:`MetricQuery` for ``/api/v1/query`` — datetimes are converted
   to Unix timestamps (``from``/``to``) the way Datadog expects.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.event_emitter import EventEmitter
from pirn.domains.connectors.capabilities.metric_query import MetricQuery
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.observability.datadog_config import DatadogConfig


class DatadogClient(ApiClient, TableSource, EventEmitter, MetricQuery):
    """Concrete :class:`ApiClient` backed by ``datadog-api-client``."""

    def __init__(
        self,
        config: DatadogConfig | None = None,
        *,
        client: Any = None,
        resource: str = "metrics",
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "DatadogClient requires either config= or client="
            )
        if not isinstance(resource, str) or not resource:
            raise ValueError(
                "DatadogClient: resource must be a non-empty string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DatadogConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured ``resource``.

        Cursor encodes Datadog's ``page[number]`` (or offset) as a
        decimal string. ``next_cursor`` is the next page index when
        Datadog reports more pages remain, else ``None``.
        """
        page_number = 0
        if cursor is not None:
            try:
                page_number = int(cursor)
            except ValueError as exc:
                raise ValueError(
                    f"DatadogClient.fetch_page: invalid cursor {cursor!r}"
                ) from exc
        params: dict[str, Any] = {"page[number]": page_number}
        if page_size is not None:
            params["page[size]"] = page_size
        path = f"/api/v1/{self._resource}"
        response = await self.request("GET", path, params=params)
        rows_obj = response.get("data") if isinstance(response, Mapping) else None
        rows = list(rows_obj or ())
        next_cursor: str | None = None
        if isinstance(response, Mapping):
            meta = response.get("meta")
            if isinstance(meta, Mapping):
                page_meta = meta.get("page")
                if isinstance(page_meta, Mapping):
                    has_more = bool(page_meta.get("has_more"))
                    if has_more:
                        next_cursor = str(page_number + 1)
        if next_cursor is None and rows and page_size is not None:
            # Fallback: continue paging while a full page was returned.
            if len(rows) >= page_size:
                next_cursor = str(page_number + 1)
        return rows, next_cursor

    async def emit(self, event: Mapping[str, Any]) -> None:
        """:class:`EventEmitter` adapter — submits a custom-metric series.

        ``event`` must contain ``metric`` (str) and ``points``
        (list of ``[timestamp, value]``). Optional: ``tags``,
        ``type``, ``host``.
        """
        if "metric" not in event or "points" not in event:
            raise ValueError(
                "DatadogClient.emit: event requires 'metric' and "
                "'points' keys"
            )
        await self.submit_metric(
            name=event["metric"],
            points=event["points"],
            tags=event.get("tags"),
        )

    async def submit_metric(
        self,
        name: str,
        points: Any,
        *,
        tags: list[str] | None = None,
    ) -> None:
        """Vendor-typed submit to ``/api/v1/series``.

        ``points`` is a list of ``[timestamp, value]`` pairs.
        """
        if not isinstance(name, str) or not name:
            raise ValueError(
                "DatadogClient.submit_metric: name must be non-empty"
            )
        series_entry: dict[str, Any] = {"metric": name, "points": list(points)}
        if tags is not None:
            series_entry["tags"] = list(tags)
        body: dict[str, Any] = {"series": [series_entry]}
        await self.request("POST", "/api/v1/series", body=body)

    async def query(
        self,
        query: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> Mapping[str, Any]:
        """:class:`MetricQuery` adapter — runs a Datadog metric query.

        Datadog's ``/api/v1/query`` requires ``from`` and ``to`` Unix
        timestamps. ``step`` is ignored (Datadog infers it from the
        window).
        """
        if not isinstance(query, str) or not query:
            raise ValueError(
                "DatadogClient.query: query must be non-empty"
            )
        if start is None or end is None:
            raise ValueError(
                "DatadogClient.query: start and end are required"
            )
        return await self.query_metrics(query, start=start, end=end)

    async def query_metrics(
        self,
        query: str,
        *,
        start: datetime,
        end: datetime,
    ) -> Mapping[str, Any]:
        """Vendor-typed query against ``/api/v1/query``."""
        params = {
            "from": int(start.timestamp()),
            "to": int(end.timestamp()),
            "query": query,
        }
        response = await self.request("GET", "/api/v1/query", params=params)
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
            raise ValueError(
                "DatadogClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "DatadogClient.request: path must be non-empty"
            )
        client = await self._ensure_client()
        method_upper = method.upper()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        def _run() -> Any:
            return client.call_api(
                method_upper,
                path,
                query_params=request_params,
                body=request_body,
                header_params=request_headers,
            )

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("datadog.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("DatadogClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from datadog_api_client import (  # type: ignore[import-not-found]
                ApiClient as DatadogApiClient,
            )
            from datadog_api_client import (
                Configuration,
            )
        except ImportError as exc:
            raise ImportError(
                "DatadogClient requires datadog-api-client; install via "
                "`pip install pirn[datadog]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "DatadogClient: missing config and no injected client"
            )

        def _build() -> Any:
            configuration = Configuration()
            if self._config.api_key is not None:
                configuration.api_key["apiKeyAuth"] = self._config.api_key
            if self._config.app_key is not None:
                configuration.api_key["appKeyAuth"] = self._config.app_key
            configuration.server_variables["site"] = self._config.site
            return DatadogApiClient(configuration)

        try:
            client = await asyncio.to_thread(_build)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("datadog.connect")
        return client
