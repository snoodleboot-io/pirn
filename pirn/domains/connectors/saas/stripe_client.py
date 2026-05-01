"""Stripe SaaS connector wrapping the synchronous ``stripe`` SDK.

Stripe's modern Python SDK ships a per-instance ``stripe.StripeClient``
that supports a generic ``raw_request`` escape hatch — used here to map
onto the :class:`ApiClient` interface. The SDK is synchronous; calls
run in a worker thread via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.stripe_config import StripeConfig


class StripeClient(ApiClient):
    """Async wrapper over the sync ``stripe.StripeClient``."""

    def __init__(
        self,
        config: StripeConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "StripeClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> StripeConfig | None:
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
                "StripeClient requires stripe; install via "
                "`pip install pirn[stripe]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "StripeClient: missing config and no injected client"
            )
        if self._config.api_key is None:
            raise ValueError("StripeClient: config.api_key is required")

        kwargs: dict[str, Any] = {"api_key": self._config.api_key}
        if self._config.api_version is not None:
            kwargs["stripe_version"] = self._config.api_version
        try:
            factory = getattr(stripe, "StripeClient")
            client = await asyncio.to_thread(factory, **kwargs)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("stripe.connect")
        return client
