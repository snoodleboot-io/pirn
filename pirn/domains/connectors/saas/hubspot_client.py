"""HubSpot SaaS connector wrapping the synchronous ``hubspot-api-client`` SDK.

The HubSpot SDK exposes resource-specific high-level methods, but it also
ships a generic ``api_request`` escape hatch that maps cleanly onto the
:class:`ApiClient` interface. The SDK is synchronous; calls run in a
worker thread via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.hubspot_config import HubSpotConfig


class HubSpotClient(ApiClient):
    """Async wrapper over the sync ``hubspot.HubSpot`` client."""

    def __init__(
        self,
        config: HubSpotConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "HubSpotClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> HubSpotConfig | None:
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
                "HubSpotClient requires hubspot-api-client; install via "
                "`pip install pirn[hubspot]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "HubSpotClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {}
        if self._config.access_token is not None:
            kwargs["access_token"] = self._config.access_token
        if self._config.api_key is not None:
            kwargs["api_key"] = self._config.api_key
        try:
            client = await asyncio.to_thread(HubSpot, **kwargs)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("hubspot.connect")
        return client
