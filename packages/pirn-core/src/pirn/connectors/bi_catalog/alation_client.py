"""Async ``ApiClient`` wrapper around the Alation REST API.

Alation uses a refresh-token + access-token flow. The simplest correct
shape — and the one used here — is to send the refresh token in the
``Token`` request header (Alation's conventional name) on every call.
Richer access-token exchange can be layered on by subclasses or by
injecting an already-authorised ``client=``.

The generic :meth:`request` forwards method/path/params/body/headers to
``httpx.AsyncClient.request`` and returns the parsed JSON body.

In addition to :meth:`request`, the client implements:

* :class:`TableSource` — :meth:`fetch_page` pages over the configured
  ``entity_type`` using Alation's ``skip``/``limit`` offset pagination.
* :class:`MetadataCatalog` — :meth:`list_entities` is an async iterator
  that pages internally, and :meth:`describe_entity` GETs the
  per-entity URL.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.bi_catalog.alation_config import AlationConfig
from pirn.connectors.capabilities.metadata_catalog import (
    MetadataCatalog,
)
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber


class AlationClient(ApiClient, TableSource, MetadataCatalog):
    """Concrete :class:`ApiClient` backed by ``httpx.AsyncClient``."""

    def __init__(
        self,
        config: AlationConfig | None = None,
        *,
        client: Any = None,
        entity_type: str = "data",
    ) -> None:
        if config is None and client is None:
            raise TypeError("AlationClient requires either config= or client=")
        if not isinstance(entity_type, str) or not entity_type:
            raise ValueError("AlationClient: entity_type must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._entity_type = entity_type
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AlationConfig | None:
        return self._config

    @property
    def entity_type(self) -> str:
        return self._entity_type

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured entity_type."""
        return await self._list_resource(self._entity_type, cursor=cursor, limit=page_size)

    async def list_entities(
        self,
        entity_type: str,
        *,
        filter: Mapping[str, Any] | None = None,
    ) -> AsyncIterator[Mapping[str, Any]]:
        """:class:`MetadataCatalog` adapter — paginates internally."""
        cursor: str | None = None
        while True:
            rows, next_cursor = await self._list_resource(entity_type, cursor=cursor, limit=None)
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
        """GET ``/integration/v1/{entity_type}/{entity_id}``."""
        return await self.request(
            "GET",
            f"/integration/v1/{self._entity_type}/{entity_id}",
        )

    async def _list_resource(
        self,
        entity_type: str,
        *,
        cursor: str | None,
        limit: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        skip = int(cursor) if cursor else 0
        page_limit = limit if limit is not None else 100
        params: dict[str, Any] = {
            "skip": skip,
            "limit": page_limit,
        }
        response = await self.request(
            "GET",
            f"/integration/v1/{entity_type}",
            params=params,
        )
        rows = self._extract_rows(response)
        next_offset = skip + page_limit
        next_cursor = str(next_offset) if len(rows) == page_limit else None
        return rows, next_cursor

    @staticmethod
    def _extract_rows(response: Any) -> list[Mapping[str, Any]]:
        if isinstance(response, list):
            return list(response)
        if isinstance(response, Mapping):
            for key in ("items", "data", "results"):
                value = response.get(key)
                if isinstance(value, list):
                    return list(value)
        return []

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
        self._logger.debug("alation.close")

    def _full_url(self, path: str) -> str:
        base = self._config.base_url if self._config is not None else None
        if path.startswith("http"):
            return path
        if base is None:
            return path
        if not path.startswith("/"):
            path = "/" + path
        return base.rstrip("/") + path

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AlationClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AlationClient requires httpx; install via `pip install pirn[alation]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("AlationClient: missing config and no injected client")
        if self._config.base_url is None:
            raise RuntimeError("AlationClient: config.base_url is required")
        if self._config.refresh_token is None:
            raise RuntimeError("AlationClient: config.refresh_token is required")
        try:
            client = httpx.AsyncClient(headers={"Token": self._config.refresh_token})
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("alation.connect")
        return client
