"""Async ``ApiClient`` wrapper around the synchronous zenpy SDK.

``Zenpy`` is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow Zendesk calls.

The connector exposes:

1. **Vendor-typed methods** for the most common reads
   (:meth:`list_tickets`, :meth:`list_users`).
2. The :class:`TableSource` capability — ``fetch_page`` pages the
   constructor's ``resource`` (default ``"tickets"``) over Zendesk's
   cursor-based pagination API.
3. The :class:`RecordWriter` capability — ``write_records`` POSTs each
   record as a ticket via ``/api/v2/tickets.json``.
4. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.capabilities.record_writer import RecordWriter
from pirn.connectors.capabilities.table_source import TableSource
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.saas.zendesk_config import ZendeskConfig


class ZendeskClient(ApiClient, TableSource, RecordWriter):
    """Concrete :class:`ApiClient` backed by ``zenpy``.

    zenpy's :class:`Zenpy` class composes domain helpers (tickets,
    users, ...). For the generic :meth:`request` interface this client
    prefers a top-level ``request(method, path, params=, body=, headers=)``
    method (test stubs supply this directly), falling back to the
    underlying ``users._call_api`` low-level helper exposed by all zenpy
    endpoint wrappers.
    """

    def __init__(
        self,
        config: ZendeskConfig | None = None,
        *,
        client: Any = None,
        resource: str = "tickets",
    ) -> None:
        if config is None and client is None:
            raise TypeError("ZendeskClient requires either config= or client=")
        if not isinstance(resource, str) or not resource:
            raise ValueError("ZendeskClient: resource must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ZendeskConfig | None:
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
        """:class:`TableSource` adapter — pages the configured resource."""
        return await self._list_resource(self._resource, cursor=cursor, page_size=page_size)

    async def list_tickets(
        self,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Zendesk tickets."""
        return await self._list_resource("tickets", cursor=cursor, page_size=page_size)

    async def list_users(
        self,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Zendesk users."""
        return await self._list_resource("users", cursor=cursor, page_size=page_size)

    async def _list_resource(
        self,
        resource: str,
        *,
        cursor: str | None,
        page_size: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        params: dict[str, Any] = {}
        if cursor is not None:
            params["page[after]"] = cursor
        if page_size is not None:
            params["page[size]"] = page_size
        response = await self.request(
            "GET",
            f"/api/v2/{resource}.json",
            params=params or None,
        )
        rows: list[Mapping[str, Any]] = []
        next_cursor: str | None = None
        if isinstance(response, Mapping):
            rows = list(response.get(resource) or ())
            meta = response.get("meta")
            if isinstance(meta, Mapping) and meta.get("has_more"):
                after_cursor = meta.get("after_cursor")
                if after_cursor is not None:
                    next_cursor = str(after_cursor)
        return rows, next_cursor

    async def write_records(
        self,
        records: Iterable[Mapping[str, Any]],
    ) -> int:
        """POST each record as a ticket via ``/api/v2/tickets.json``."""
        materialised = list(records)
        for record in materialised:
            await self.request("POST", "/api/v2/tickets.json", body=record)
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
        client = await self._ensure_client()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        def _run() -> Any:
            top_level = getattr(client, "request", None)
            if callable(top_level):
                return top_level(
                    method,
                    path,
                    params=request_params,
                    body=request_body,
                    headers=request_headers,
                )
            users = getattr(client, "users", None)
            call_api = getattr(users, "_call_api", None) if users else None
            if callable(call_api):
                return call_api(
                    method,
                    path,
                    params=request_params,
                    body=request_body,
                )
            raise RuntimeError(
                "ZendeskClient: underlying client exposes no usable request entry-point"
            )

        try:
            return await asyncio.to_thread(_run)
        except RuntimeError:
            raise
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("zendesk.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("ZendeskClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from zenpy import Zenpy  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "ZendeskClient requires zenpy; install via `pip install pirn[zendesk]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("ZendeskClient: missing config and no injected client")

        creds: dict[str, Any] = {}
        if self._config.subdomain is not None:
            creds["subdomain"] = self._config.subdomain
        if self._config.email is not None:
            creds["email"] = self._config.email
        if self._config.api_token is not None:
            creds["token"] = self._config.api_token
        if self._config.oauth_token is not None:
            creds["oauth_token"] = self._config.oauth_token

        try:
            client = await asyncio.to_thread(Zenpy, **creds)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("zendesk.connect")
        return client
