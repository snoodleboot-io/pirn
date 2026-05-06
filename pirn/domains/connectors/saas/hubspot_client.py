"""HubSpot SaaS connector wrapping the synchronous ``hubspot-api-client`` SDK.

The HubSpot SDK exposes resource-specific high-level methods, but it also
ships a generic ``api_request`` escape hatch that maps cleanly onto the
:class:`ApiClient` interface. The SDK is synchronous; calls run in a
worker thread via :func:`asyncio.to_thread`.

The connector exposes:

1. **Vendor-typed methods** for the most common reads
   (:meth:`list_objects`).
2. The :class:`TableSource` capability — ``fetch_page`` pages the
   constructor's ``object_type`` over HubSpot's CRM objects API.
3. The :class:`RecordWriter` capability — ``write_records`` POSTs each
   record to ``/crm/v3/objects/<object_type>``.
4. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.record_writer import RecordWriter
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.hubspot_config import HubSpotConfig


class HubSpotClient(ApiClient, TableSource, RecordWriter):
    """Async wrapper over the sync ``hubspot.HubSpot`` client."""

    def __init__(
        self,
        config: HubSpotConfig | None = None,
        *,
        client: Any = None,
        object_type: str = "contacts",
    ) -> None:
        if config is None and client is None:
            raise TypeError("HubSpotClient requires either config= or client=")
        if not isinstance(object_type, str) or not object_type:
            raise ValueError("HubSpotClient: object_type must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._object_type = object_type
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> HubSpotConfig | None:
        return self._config

    @property
    def object_type(self) -> str:
        return self._object_type

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured object type."""
        return await self.list_objects(self._object_type, after=cursor, limit=page_size)

    async def list_objects(
        self,
        object_type: str,
        *,
        after: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of a HubSpot CRM object collection.

        Returns ``(rows, next_cursor)`` where ``next_cursor`` is the
        ``paging.next.after`` token when HubSpot signals more results,
        else ``None``.
        """
        if not isinstance(object_type, str) or not object_type:
            raise ValueError("HubSpotClient.list_objects: object_type must be a non-empty string")
        params: dict[str, Any] = {}
        if after is not None:
            params["after"] = after
        if limit is not None:
            params["limit"] = limit
        response = await self.request(
            "GET",
            f"/crm/v3/objects/{object_type}",
            params=params or None,
        )
        rows: list[Mapping[str, Any]] = []
        next_cursor: str | None = None
        if isinstance(response, Mapping):
            rows = list(response.get("results") or ())
            paging = response.get("paging")
            if isinstance(paging, Mapping):
                next_block = paging.get("next")
                if isinstance(next_block, Mapping):
                    after_token = next_block.get("after")
                    if after_token is not None:
                        next_cursor = str(after_token)
        return rows, next_cursor

    async def write_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> int:
        """POST each record to ``/crm/v3/objects/<object_type>``; return count."""
        materialised = list(records)
        path = f"/crm/v3/objects/{self._object_type}"
        for record in materialised:
            await self.request("POST", path, body=record)
        return len(materialised)

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
            raise ValueError("HubSpotClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("HubSpotClient.request: path must be non-empty")
        client = await self._ensure_client()
        payload: dict[str, Any] = {
            "method": method.upper(),
            "path": path,
        }
        if params is not None:
            payload["qs"] = dict(params)
        if body is not None:
            payload["body"] = dict(body)
        if headers is not None:
            payload["headers"] = dict(headers)

        def _run() -> Any:
            return client.api_request(payload)

        return await asyncio.to_thread(_run)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("hubspot.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("HubSpotClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from hubspot import HubSpot  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "HubSpotClient requires hubspot-api-client; install via `pip install pirn[hubspot]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("HubSpotClient: missing config and no injected client")

        kwargs: dict[str, Any] = {}
        if self._config.access_token is not None:
            kwargs["access_token"] = self._config.access_token
        if self._config.api_key is not None:
            kwargs["api_key"] = self._config.api_key
        try:
            client = await asyncio.to_thread(HubSpot, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("hubspot.connect")
        return client
