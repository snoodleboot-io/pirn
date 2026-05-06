"""Stripe SaaS connector wrapping the synchronous ``stripe`` SDK.

Stripe's modern Python SDK ships a per-instance ``stripe.StripeClient``.
The connector exposes:

1. **Vendor-typed methods** for the most common reads
   (:meth:`list_charges`, :meth:`list_customers`).
2. The :class:`TableSource` capability, which routes ``fetch_page`` to
   ``list_charges`` by default. Override the default by passing
   ``object_type=`` to the constructor for a different Stripe list
   endpoint.
3. The legacy :meth:`request` escape hatch (forwards to
   ``stripe.StripeClient.raw_request``) for cases the typed surface
   does not cover.

The SDK is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.table_source import TableSource
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.stripe_config import StripeConfig


class StripeClient(ApiClient, TableSource):
    """Async wrapper over the sync ``stripe.StripeClient``."""

    def __init__(
        self,
        config: StripeConfig | None = None,
        *,
        client: Any = None,
        object_type: str = "charges",
    ) -> None:
        if config is None and client is None:
            raise TypeError("StripeClient requires either config= or client=")
        if not isinstance(object_type, str) or not object_type:
            raise ValueError("StripeClient: object_type must be a non-empty string")
        self._config = config
        self._client = client
        self._closed = False
        self._object_type = object_type
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> StripeConfig | None:
        return self._config

    @property
    def object_type(self) -> str:
        return self._object_type

    async def list_charges(
        self,
        *,
        starting_after: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Stripe charges.

        Returns ``(charges, next_cursor)`` where ``next_cursor`` is the
        id of the last charge if Stripe says more pages remain, else
        ``None``. ``starting_after`` is Stripe's cursor parameter.
        """
        return await self._list_object("charges", starting_after=starting_after, limit=limit)

    async def list_customers(
        self,
        *,
        starting_after: str | None = None,
        limit: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """Vendor-typed read of Stripe customers (same shape as :meth:`list_charges`)."""
        return await self._list_object("customers", starting_after=starting_after, limit=limit)

    async def fetch_page(
        self,
        cursor: str | None = None,
        *,
        page_size: int | None = None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        """:class:`TableSource` adapter — pages the configured ``object_type``."""
        return await self._list_object(
            self._object_type,
            starting_after=cursor,
            limit=page_size,
        )

    async def _list_object(
        self,
        object_type: str,
        *,
        starting_after: str | None,
        limit: int | None,
    ) -> tuple[list[Mapping[str, Any]], str | None]:
        params: dict[str, Any] = {}
        if starting_after is not None:
            params["starting_after"] = starting_after
        if limit is not None:
            params["limit"] = limit
        response = await self.request("GET", f"/v1/{object_type}", params=params or None)
        rows = list(response.get("data") or ())
        has_more = bool(response.get("has_more"))
        next_cursor = rows[-1].get("id") if has_more and rows else None
        return rows, next_cursor

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
            raise ValueError("StripeClient.request: method must be non-empty")
        if not isinstance(path, str) or not path:
            raise ValueError("StripeClient.request: path must be non-empty")
        client = await self._ensure_client()
        upper_method = method.upper()
        params_dict = dict(params) if params is not None else None
        body_dict = dict(body) if body is not None else None
        headers_dict = dict(headers) if headers is not None else None

        def _run() -> Any:
            return client.raw_request(
                upper_method,
                path,
                params=params_dict,
                body=body_dict,
                headers=headers_dict,
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
        self._logger.debug("stripe.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("StripeClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import stripe  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "StripeClient requires stripe; install via `pip install pirn[stripe]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("StripeClient: missing config and no injected client")
        if self._config.api_key is None:
            raise ValueError("StripeClient: config.api_key is required")

        kwargs: dict[str, Any] = {"api_key": self._config.api_key}
        if self._config.api_version is not None:
            kwargs["stripe_version"] = self._config.api_version
        try:
            factory = stripe.StripeClient
            client = await asyncio.to_thread(factory, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("stripe.connect")
        return client
