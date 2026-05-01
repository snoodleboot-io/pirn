"""Async ``ApiClient`` wrapper around the synchronous Twilio SDK.

``twilio.rest.Client`` is sync; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on slow Twilio calls.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.twilio_config import TwilioConfig


class TwilioClient(ApiClient):
    """Concrete :class:`ApiClient` backed by the Twilio Python SDK.

    The Twilio :class:`Client` exposes a low-level
    ``request(method, uri, params=..., data=..., headers=...)`` used for
    the generic :meth:`request` interface. Tests inject a stub client
    that mirrors that surface.
    """

    def __init__(
        self,
        config: TwilioConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("TwilioClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> TwilioConfig | None:
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
            return client.request(
                method,
                path,
                params=request_params,
                data=request_body,
                headers=request_headers,
            )

        try:
            return await asyncio.to_thread(_run)
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._closed = True
        self._logger.debug("twilio.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("TwilioClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from twilio.rest import Client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "TwilioClient requires the twilio SDK; install via "
                "`pip install pirn[twilio]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "TwilioClient: missing config and no injected client"
            )

        kwargs: dict[str, Any] = {}
        if self._config.region is not None:
            kwargs["region"] = self._config.region

        try:
            client = await asyncio.to_thread(
                Client,
                self._config.account_sid,
                self._config.auth_token,
                **kwargs,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("twilio.connect")
        return client
