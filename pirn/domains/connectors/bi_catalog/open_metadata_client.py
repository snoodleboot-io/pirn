"""Async ``ApiClient`` wrapper around the OpenMetadata REST API.

Uses ``httpx.AsyncClient`` with a bearer-token ``Authorization`` header
populated from ``config.jwt_token``. The generic :meth:`request` forwards
method/path/params/body/headers to ``client.request`` and returns the
parsed JSON body.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``entity_type`` using OpenMetadata's ``after`` cursor.
* :class:`MetadataCatalog` — :meth:`list_entities` is an async iterator
  that pages internally, and :meth:`describe_entity` GETs
  ``/api/v1/entities/{id}``.
* Vendor-typed shortcuts :meth:`list_tables` and :meth:`list_dashboards`.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.open_metadata_config import (
    OpenMetadataConfig,
)
from pirn.domains.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class OpenMetadataClient(ApiClient, TableSource, MetadataCatalog):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: OpenMetadataConfig | None = None,
        *,
        client: Any = None,
        entity_type: str = "tables",
    ) -> None:
        if config is None and client is None:
            raise TypeError("OpenMetadataClient requires either config= or client=")
        if not isinstance(entity_type, str) or not entity_type:
            raise ValueError("OpenMetadataClient: entity_type must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._entity_type = entity_type
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OpenMetadataConfig | None:
        return self._config

    @property
    def entity_type(self) -> str:
        return self._entity_type

    async def list_tables(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of OpenMetadata tables."""
        return await self._list_resource("tables", after=after, limit=limit)

    async def list_dashboards(
        self,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of OpenMetadata dashboards."""
        return await self._list_resource("dashboards", after=after, limit=limit)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured entity_type."""
        return await self._list_resource(self._entity_type, after=cursor, limit=page_size)

    async def list_entities(
        self,
        entity_type: str,
        *,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """:class:`MetadataCatalog` adapter — paginates internally."""
        cursor: str | None = None
        while True:
            rows, next_cursor = await self._list_resource(entity_type, after=cursor, limit=None)
            for entity in rows:
                if filter is None or self._matches_filter(entity, filter):
                    yield entity
            if next_cursor is None:
                return
            cursor = next_cursor

    async def describe_entity(
        self,
        entity_id: str,
    ) -> Mapping[str, Any]:
        """GET ``/api/v1/entities/{id}``."""
        return await self.request("GET", f"/api/v1/entities/{entity_id}")

    async def _list_resource(
        self,
        entity_type: str,
        *,
        after: str | None,
        limit: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        params: dict[str, Any] = {}
        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        response = await self.request(
            "GET",
            f"/api/v1/{entity_type}",
            params=params or None,
        )
        rows: list[Mapping[str, Any]] = list(response.get("data") or [])
        paging = response.get("paging") or {}
        next_cursor = paging.get("after")
        return rows, next_cursor if next_cursor else None

    @staticmethod
    def _matches_filter(entity: Mapping[str, Any], filter: Mapping[str, Any]) -> bool:
        for key, value in filter.items():
            if entity.get(key) != value:
                return False
        return True

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
        self._logger.debug("open_metadata.close")

    def _full_url(self, path: str) -> str:
        base = self._config.host_url if self._config is not None else None
        if path.startswith("http"):
            return path
        if base is None:
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("OpenMetadataClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OpenMetadataClient requires httpx; install via `pip install pirn[open-metadata]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("OpenMetadataClient: missing config and no injected client")
        if self._config.host_url is None:
            raise RuntimeError("OpenMetadataClient: config.host_url is required")
        if self._config.jwt_token is None:
            raise RuntimeError("OpenMetadataClient: config.jwt_token is required")
        try:
            client = httpx.AsyncClient(
                headers={"Authorization": f"Bearer {self._config.jwt_token}"}
            )
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("open_metadata.connect")
        return client
