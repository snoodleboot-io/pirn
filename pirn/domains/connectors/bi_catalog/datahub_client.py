"""Async ``ApiClient`` wrapper around the DataHub REST + GraphQL surfaces.

Uses ``httpx.AsyncClient`` with a bearer-token ``Authorization`` header
when ``config.token`` is provided. The generic :meth:`request` forwards
method/path/params/body/headers to ``client.request`` and returns the
parsed JSON body — both REST endpoints and the ``/api/graphql`` endpoint
return JSON, so a single shape suffices.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``entity_type`` using DataHub's offset-based search.
* :class:`MetadataCatalog` — :meth:`list_entities` is an async iterator
  that pages internally, and :meth:`describe_entity` GETs
  ``/entity/{urn}``.
* Vendor-typed :meth:`search_entities` returning
  ``(entities, next_cursor)`` so callers that already know they're on
  DataHub can read the typed surface.
"""

from __future__ import annotations

import logging
from typing import Any, AsyncIterator, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.bi_catalog.datahub_config import DataHubConfig
from pirn.domains.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class DataHubClient(ApiClient, TableSource, MetadataCatalog):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: DataHubConfig | None = None,
        *,
        client: Any = None,
        entity_type: str = "dataset",
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "DataHubClient requires either config= or client="
            )
        if not isinstance(entity_type, str) or not entity_type:
            raise ValueError(
                "DataHubClient: entity_type must be a non-empty string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._entity_type = entity_type
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DataHubConfig | None:
        return self._config

    @property
    def entity_type(self) -> str:
        return self._entity_type

    async def search_entities(
        self,
        entity_type: str,
        query: str = "*",
        *,
        start: int = 0,
        count: int = 100,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed offset/limit search over DataHub entities.

        Returns ``(entities, next_cursor)`` where ``next_cursor`` is
        ``str(start + count)`` if more results remain, else ``None``.
        """
        params: dict[str, Any] = {
            "entity": entity_type,
            "query": query,
            "start": start,
            "count": count,
        }
        response = await self.request(
            "GET", "/entities", params=params
        )
        entities = list(response.get("entities") or ())
        total = int(response.get("total") or 0)
        next_offset = start + count
        next_cursor = str(next_offset) if next_offset < total else None
        return entities, next_cursor

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured entity_type."""
        start = int(cursor) if cursor else 0
        count = page_size if page_size is not None else 100
        return await self.search_entities(
            self._entity_type, "*", start=start, count=count
        )

    async def list_entities(
        self,
        entity_type: str,
        *,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """:class:`MetadataCatalog` adapter — paginates internally."""
        cursor: str | None = None
        while True:
            entities, next_cursor = await self.search_entities(
                entity_type,
                "*",
                start=int(cursor) if cursor else 0,
                count=100,
            )
            for entity in entities:
                if filter is None or self._matches_filter(entity, filter):
                    yield entity
            if next_cursor is None:
                return
            cursor = next_cursor

    async def describe_entity(
        self,
        entity_id: str,
    ) -> Mapping[str, Any]:
        """GET ``/entity/{urn}`` and return the parsed JSON body."""
        return await self.request("GET", f"/entity/{entity_id}")

    @staticmethod
    def _matches_filter(
        entity: Mapping[str, Any], filter: Mapping[str, Any]
    ) -> bool:
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
                await aclose_fn()
            self._client = None
        self._closed = True
        self._logger.debug("datahub.close")

    def _full_url(self, path: str) -> str:
        base = self._config.gms_url if self._config is not None else None
        if path.startswith("http"):
            return path
        if base is None:
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("DataHubClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DataHubClient requires httpx; install via "
                "`pip install pirn[datahub]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "DataHubClient: missing config and no injected client"
            )
        if self._config.gms_url is None:
            raise RuntimeError("DataHubClient: config.gms_url is required")
        kwargs: dict[str, Any] = {}
        if self._config.token is not None:
            kwargs["headers"] = {
                "Authorization": f"Bearer {self._config.token}"
            }
        try:
            client = httpx.AsyncClient(**kwargs)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("datahub.connect")
        return client
