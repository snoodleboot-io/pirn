"""Async ``ApiClient`` wrapper around the Grafana HTTP REST API.

Grafana exposes a fully-documented HTTP REST API at
``/api/dashboards``, ``/api/datasources``, ``/api/folders`` etc.
Authentication uses a bearer token (API key or service-account token).
The connector uses :mod:`httpx` directly (``pirn[grafana]`` extra
declares the dependency).

Capabilities exposed:

1. :class:`TableSource` — paginated reads of dashboards, folders or
   datasources. The configured ``resource`` (``"dashboards"`` by
   default, ``"folders"`` or ``"datasources"``) selects the endpoint.
   Cursor encodes the page index as a decimal string.
2. :class:`MetricQuery` — Grafana's unified ``/api/ds/query`` endpoint.
   The constructor accepts ``datasource_uid`` which is forwarded in the
   request body.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.capabilities.metric_query import MetricQuery
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.observability.grafana_config import GrafanaConfig


class GrafanaClient(ApiClient, TableSource, MetricQuery):
    """Concrete :class:`ApiClient` for the Grafana HTTP REST API."""

    def __init__(
        self,
        config: GrafanaConfig | None = None,
        *,
        client: Any = None,
        resource: str = "dashboards",
        datasource_uid: str | None = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("GrafanaClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError("GrafanaClient: resource must be a non-empty string")
        if resource not in ("dashboards", "folders", "datasources"):
            raise ValueError(
                "GrafanaClient: resource must be one of "
                "'dashboards', 'folders', 'datasources'; got "
                f"{resource!r}"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._datasource_uid = datasource_uid
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GrafanaConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    @property
    def datasource_uid(self) -> str | None:
        return self._datasource_uid

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured resource.

        ``cursor`` encodes Grafana's 1-based page number as a decimal
        string. ``next_cursor`` is the next page index when a full
        page was returned, else ``None``.
        """
        page = 1
        if cursor is not None:
            try:
                page = int(cursor)
            except ValueError as exc:
                raise ValueError(f"GrafanaClient.fetch_page: invalid cursor {cursor!r}") from exc
        if self._resource == "dashboards":
            return await self.list_dashboards(page=page, limit=page_size or 100)
        if self._resource == "folders":
            return await self.list_folders(page=page, limit=page_size or 100)
        return await self.list_datasources(page=page, limit=page_size or 100)

    async def list_dashboards(
        self,
        *,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed dashboard search via ``/api/search``."""
        params = {"type": "dash-db", "page": page, "limit": limit}
        response = await self.request("GET", "/api/search", params=params)
        rows: list[Mapping[str, Any]] = list(response or [])
        next_cursor = str(page + 1) if len(rows) >= limit else None
        return rows, next_cursor

    async def list_folders(
        self,
        *,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed folder list via ``/api/folders``."""
        params = {"page": page, "limit": limit}
        response = await self.request("GET", "/api/folders", params=params)
        rows: list[Mapping[str, Any]] = list(response or [])
        next_cursor = str(page + 1) if len(rows) >= limit else None
        return rows, next_cursor

    async def list_datasources(
        self,
        *,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed datasource list via ``/api/datasources``.

        Grafana's ``/api/datasources`` does not paginate server-side;
        we slice the list client-side based on ``page``/``limit`` so
        the :class:`TableSource` contract is honoured.
        """
        response = await self.request("GET", "/api/datasources")
        all_rows: list[Mapping[str, Any]] = list(response or [])
        offset = max(page - 1, 0) * limit
        rows = all_rows[offset : offset + limit]
        next_cursor = str(page + 1) if offset + limit < len(all_rows) else None
        return rows, next_cursor

    async def query(
        self,
        query: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        step: str | None = None,
    ) -> Mapping[str, Any]:
        """:class:`MetricQuery` adapter — Grafana ``/api/ds/query``.

        Grafana wants a structured datasource reference. The connector
        requires a ``datasource_uid`` (constructor argument) and
        forwards ``query`` as the ``expr`` field in the query body.
        Datetimes are converted to milliseconds since epoch (Grafana's
        format).
        """
        if not isinstance(query, str) or not query:
            raise ValueError("GrafanaClient.query: query must be non-empty")
        if self._datasource_uid is None:
            raise RuntimeError(
                "GrafanaClient.query: datasource_uid is required; pass it to the constructor"
            )
        body: dict[str, Any] = {
            "queries": [
                {
                    "refId": "A",
                    "datasource": {"uid": self._datasource_uid},
                    "expr": query,
                    **({"interval": step} if step is not None else {}),
                }
            ]
        }
        if start is not None:
            body["from"] = str(int(start.timestamp() * 1000))
        if end is not None:
            body["to"] = str(int(end.timestamp() * 1000))
        response = await self.request("POST", "/api/ds/query", body=body)
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
            raise ValueError("GrafanaClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("GrafanaClient.request: path must be non-empty")
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
        self._logger.debug("grafana.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("GrafanaClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "GrafanaClient requires httpx; install via `pip install pirn[grafana]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("GrafanaClient: missing config and no injected client")
        if self._config.base_url is None:
            raise RuntimeError("GrafanaClient: config.base_url is required")

        client_headers: dict[str, str] = {}
        if self._config.api_key is not None:
            client_headers["Authorization"] = f"Bearer {self._config.api_key}"

        try:
            client = httpx.AsyncClient(
                base_url=self._config.base_url.rstrip("/"),
                headers=client_headers or None,
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("grafana.connect")
        return client
