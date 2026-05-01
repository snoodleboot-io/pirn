"""Shopify SaaS connector wrapping the synchronous ``ShopifyAPI`` SDK.

ShopifyAPI follows ActiveResource patterns and exposes a low-level
``ShopifyResource.connection`` HTTP client. For the generic
:class:`ApiClient` interface the connector delegates to that connection's
``request`` method. The SDK is synchronous; calls run in a worker
thread via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.shopify_config import ShopifyConfig


class ShopifyClient(ApiClient):
    """Async wrapper over the sync ``shopify`` SDK connection."""

    def __init__(
        self,
        config: ShopifyConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "ShopifyClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ShopifyConfig | None:
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
            raise ValueError("ShopifyClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("ShopifyClient.request: path must be non-empty")
        client = await self._ensure_client()
        upper_method = method.upper()
        full_path = self._build_path(path, params)
        headers_dict = dict(headers) if headers is not None else {}
        body_dict = dict(body) if body is not None else None

        def _run() -> Any:
            return client.request(
                upper_method,
                full_path,
                headers=headers_dict,
                data=body_dict,
            )

        return await asyncio.to_thread(_run)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._closed = True
        self._logger.debug("shopify.close")

    @staticmethod
    def _build_path(path: str, params: Mapping[str, Any] | None) -> str:
        if not params:
            return path
        encoded = "&".join(f"{k}={v}" for k, v in params.items())
        separator = "&" if "?" in path else "?"
        return f"{path}{separator}{encoded}"

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("ShopifyClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import shopify  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "ShopifyClient requires ShopifyAPI; install via "
                "`pip install pirn[shopify]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "ShopifyClient: missing config and no injected client"
            )
        if self._config.shop_url is None:
            raise ValueError("ShopifyClient: config.shop_url is required")
        if self._config.access_token is None:
            raise ValueError("ShopifyClient: config.access_token is required")

        shop_url = self._config.shop_url
        access_token = self._config.access_token
        api_version = self._config.api_version

        def _connect() -> Any:
            session = shopify.Session(shop_url, api_version, access_token)
            shopify.ShopifyResource.activate_session(session)
            return shopify.ShopifyResource.connection

        try:
            client = await asyncio.to_thread(_connect)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("shopify.connect")
        return client
