"""Async ``ApiClient`` wrapper around the synchronous zenpy SDK.

``Zenpy`` is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow Zendesk calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.zendesk_config import ZendeskConfig


class ZendeskClient(ApiClient):
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
    ) -> None:
        if config is None and client is None:
            raise TypeError("ZendeskClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ZendeskConfig | None:
        return self._config

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
                "ZendeskClient: underlying client exposes no usable "
                "request entry-point"
            )

        try:
            return await asyncio.to_thread(_run)
        except RuntimeError:
            raise
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
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
                "ZendeskClient requires zenpy; install via "
                "`pip install pirn[zendesk]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "ZendeskClient: missing config and no injected client"
            )

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
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("zendesk.connect")
        return client
