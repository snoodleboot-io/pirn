"""Shopify SaaS connector wrapping the synchronous ``ShopifyAPI`` SDK.

ShopifyAPI follows ActiveResource patterns and exposes a low-level
``ShopifyResource.connection`` HTTP client. For the generic
:class:`ApiClient` interface the connector delegates to that connection's
``request`` method. The SDK is synchronous; calls run in a worker
thread via :func:`asyncio.to_thread`.

The connector exposes:

1. **Vendor-typed methods** for the most common reads
   (:meth:`list_orders`, :meth:`list_products`).
2. The :class:`TableSource` capability — ``fetch_page`` pages the
   constructor's ``resource`` (default ``"orders"``) using Shopify's
   cursor-based ``page_info`` pagination. The cursor is extracted from
   the response's ``Link`` header (``rel="next"``).
3. The legacy :meth:`request` escape hatch.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.shopify_config import ShopifyConfig


class ShopifyClient(ApiClient, TableSource):
    """Async wrapper over the sync ``shopify`` SDK connection."""

    def __init__(
        self,
        config: ShopifyConfig | None = None,
        *,
        client: Any = None,
        resource: str = "orders",
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "ShopifyClient requires either config= or client="
            )
        if not isinstance(resource, str) or not resource:
            raise ValueError(
                "ShopifyClient: resource must be a non-empty string"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._resource = resource
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ShopifyConfig | None:
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
        return await self._list_resource(
            self._resource, cursor=cursor, page_size=page_size
        )

    async def list_orders(
        self,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Shopify orders."""
        return await self._list_resource(
            "orders", cursor=cursor, page_size=page_size
        )

    async def list_products(
        self,
        *,
        cursor: str | None = None,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Shopify products."""
        return await self._list_resource(
            "products", cursor=cursor, page_size=page_size
        )

    async def _list_resource(
        self,
        resource: str,
        *,
        cursor: str | None,
        page_size: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        api_version = self._api_version_or_default()
        path = f"/admin/api/{api_version}/{resource}.json"
        params: dict[str, Any] = {}
        if cursor is not None:
            params["page_info"] = cursor
        if page_size is not None:
            params["limit"] = page_size
        full_path = self._build_path(path, params or None)
        response = await self._raw_request("GET", full_path)
        body = self._extract_body(response)
        rows: list[Mapping[str, Any]] = []
        if isinstance(body, Mapping):
            rows = list(body.get(resource) or ())
        next_cursor = self._extract_next_cursor(response, body)
        return rows, next_cursor

    async def _raw_request(
        self,
        method: str,
        full_path: str,
        *,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        client = await self._ensure_client()
        upper_method = method.upper()
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

    def _api_version_or_default(self) -> str:
        if self._config is not None and self._config.api_version:
            return self._config.api_version
        return "2024-04"

    @staticmethod
    def _extract_body(response: Any) -> Any:
        if isinstance(response, Mapping):
            return response
        body_attr = getattr(response, "body", None)
        if body_attr is not None:
            return body_attr
        return response

    @classmethod
    def _extract_next_cursor(
        cls, response: Any, body: Any
    ) -> str | None:
        link_header = cls._extract_link_header(response, body)
        if link_header:
            cursor = cls._parse_link_header_cursor(link_header)
            if cursor is not None:
                return cursor
        if isinstance(body, Mapping):
            page_info = body.get("page_info")
            if page_info:
                return str(page_info)
        return None

    @staticmethod
    def _extract_link_header(response: Any, body: Any) -> str | None:
        headers = getattr(response, "headers", None)
        if isinstance(headers, Mapping):
            link = headers.get("Link") or headers.get("link")
            if link:
                return str(link)
        if isinstance(response, Mapping):
            link = response.get("Link") or response.get("link")
            if link:
                return str(link)
        if isinstance(body, Mapping):
            link = body.get("Link") or body.get("link")
            if link:
                return str(link)
        return None

    @staticmethod
    def _parse_link_header_cursor(link_header: str) -> str | None:
        # Shopify Link header form: <url?page_info=XYZ>; rel="next", <...>; rel="previous"
        for part in link_header.split(","):
            segment = part.strip()
            if 'rel="next"' not in segment and "rel='next'" not in segment:
                continue
            url_match = re.search(r"<([^>]+)>", segment)
            if not url_match:
                continue
            url = url_match.group(1)
            page_match = re.search(r"[?&]page_info=([^&]+)", url)
            if page_match:
                return page_match.group(1)
        return None

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
        self._clear_credentials()
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
            self._reraise_scrubbed(exc)
        self._logger.debug("shopify.connect")
        return client
