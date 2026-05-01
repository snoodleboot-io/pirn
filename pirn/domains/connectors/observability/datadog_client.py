"""Async ``ApiClient`` wrapper around the synchronous ``datadog-api-client`` SDK.

The Datadog SDK is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime. The generic :meth:`request` is implemented against the SDK's
low-level ``call_api(method, path, ...)`` so test stubs only need to
expose that single hook (mirrors the SDK's
``datadog_api_client.ApiClient`` shape).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.observability.datadog_config import DatadogConfig


class DatadogClient(ApiClient):
    """Concrete :class:`ApiClient` backed by ``datadog-api-client``."""

    def __init__(
        self,
        config: DatadogConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "DatadogClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DatadogConfig | None:
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
            raise ValueError(
                "DatadogClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "DatadogClient.request: path must be non-empty"
            )
        client = await self._ensure_client()
        method_upper = method.upper()
        request_params = dict(params) if params is not None else None
        request_body = dict(body) if body is not None else None
        request_headers = dict(headers) if headers is not None else None

        def _run() -> Any:
            return client.call_api(
                method_upper,
                path,
                query_params=request_params,
                body=request_body,
                header_params=request_headers,
            )

        try:
            return await asyncio.to_thread(_run)
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
        self._logger.debug("datadog.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("DatadogClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from datadog_api_client import (  # type: ignore[import-not-found]
                ApiClient as DatadogApiClient,
                Configuration,
            )
        except ImportError as exc:
            raise ImportError(
                "DatadogClient requires datadog-api-client; install via "
                "`pip install pirn[datadog]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "DatadogClient: missing config and no injected client"
            )

        def _build() -> Any:
            configuration = Configuration()
            if self._config.api_key is not None:
                configuration.api_key["apiKeyAuth"] = self._config.api_key
            if self._config.app_key is not None:
                configuration.api_key["appKeyAuth"] = self._config.app_key
            configuration.server_variables["site"] = self._config.site
            return DatadogApiClient(configuration)

        try:
            client = await asyncio.to_thread(_build)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("datadog.connect")
        return client
