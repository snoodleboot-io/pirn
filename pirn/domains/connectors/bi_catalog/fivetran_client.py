"""Async ``ApiClient`` wrapper around the Fivetran REST API.

Uses ``httpx.AsyncClient`` with HTTP Basic auth (``api_key`` / ``api_secret``).
The generic :meth:`request` forwards ``method``/``path``/``params``/``body``/
``headers`` to ``client.request`` and returns the parsed JSON body.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``resource`` (``connectors``, ``groups``, ``users``) using Fivetran's
  cursor-based pagination.
* Vendor-typed shortcuts :meth:`list_connectors` and :meth:`list_groups`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.fivetran_config import FivetranConfig
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class FivetranClient(ApiClient, TableSource):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: FivetranConfig | None = None,
        *,
        client: Any = None,
        resource: str = "connectors",
    ) -> None:
        if config is None and client is None:
            raise TypeError("FivetranClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError("FivetranClient: resource must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> FivetranConfig | None:
        return self._config

    @property
    def resource(self) -> str:
        return self._resource

    async def list_connectors(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Fivetran connectors."""
        return await self._list_resource("connectors", cursor=cursor, limit=limit)

    async def list_groups(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Fivetran groups."""
        return await self._list_resource("groups", cursor=cursor, limit=limit)

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
        params: dict[str, Any] = {}
        if cursor is not None:
            params["cursor"] = cursor
        if limit is not None:
            params["limit"] = limit
        response = await self.request("GET", f"/{resource}", params=params or None)
        data = response.get("data") or {}
        rows = list(data.get("items") or ())
        next_cursor = data.get("next_cursor")
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
                await aclose_fn()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("fivetran.close")

    def _full_url(self, path: str) -> str:
        base = self._config.base_url if self._config is not None else ""
        if not path.startswith("/") and not path.startswith("http"):
            path = "/" + path
        if path.startswith("http"):
            return path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("FivetranClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "FivetranClient requires httpx; install via `pip install pirn[fivetran]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("FivetranClient: missing config and no injected client")
        if self._config.api_key is None or self._config.api_secret is None:
            raise RuntimeError("FivetranClient: config.api_key and config.api_secret are required")
        try:
            client = httpx.AsyncClient(
                auth=httpx.BasicAuth(self._config.api_key, self._config.api_secret)
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("fivetran.connect")
        return client
