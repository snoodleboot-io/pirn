"""Async ``ApiClient`` wrapper around the Airbyte REST API.

Uses ``httpx.AsyncClient`` with a bearer-token ``Authorization`` header.
``request`` forwards method/path/params/body/headers to ``client.request``
and returns the parsed JSON body.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``resource`` (``connections``, ``workspaces``, ...) using Airbyte
  Cloud's POST-based listing.
* Vendor-typed shortcuts :meth:`list_connections` and
  :meth:`list_workspaces`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.bi_catalog.airbyte_config import AirbyteConfig
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber


class AirbyteClient(ApiClient, TableSource):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: AirbyteConfig | None = None,
        *,
        client: Any = None,
        resource: str = "connections",
    ) -> None:
        if config is None and client is None:
            raise TypeError("AirbyteClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError("AirbyteClient: resource must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AirbyteConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    async def list_connections(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Airbyte connections."""
        return await self._list_resource("connections", cursor=cursor, limit=limit)

    async def list_workspaces(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Airbyte workspaces."""
        return await self._list_resource("workspaces", cursor=cursor, limit=limit)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured resource."""
        return await self._list_resource(self._resource, cursor=cursor, limit=page_size)

    async def _list_resource(
        self,
        resource: str,
        *,
        cursor: str | None,
        limit: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        body: dict[str, Any] = {}
        if limit is not None:
            body["limit"] = limit
        if cursor is not None:
            body["cursor"] = cursor
        response = await self.request(
            "POST",
            f"/v1/{resource}/list",
            body=body or None,
        )
        rows: list[Mapping[str, Any]] = list(response.get("data") or [])
        next_cursor = response.get("next_cursor")
        return rows, next_cursor if next_cursor else None

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        client = await self._ensure_client()
        url = self._full_url(path)
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None
        try:
            response = await client.request(
                method.upper(),
                url,
                params=request_params,
                json=request_body,
                headers=request_headers,
            )
            return response.json()
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

    async def close(self) -> None:
        if self._client is not None:
            aclose_fn = getattr(self._client, "aclose", None)
            if callable(aclose_fn):
                await aclose_fn()  # type: ignore[misc]
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("airbyte.close")

    def _full_url(self, path: str) -> str:
        base = self._config.base_url if self._config is not None else ""
        if path.startswith("http"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AirbyteClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AirbyteClient requires httpx; install via `pip install pirn[airbyte]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("AirbyteClient: missing config and no injected client")
        if self._config.access_token is None:
            raise RuntimeError(
                "AirbyteClient: config.access_token is required (OAuth2 "
                "exchange not yet implemented in this connector)"
            )
        token = self._config.access_token
        try:
            client = httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"})
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("airbyte.connect")
        return client
