"""Amplitude Analytics ingestion connector wrapping the sync ``Amplitude`` SDK.

The official ``amplitude-analytics`` SDK is synchronous and
ingestion-only; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop. The generic :meth:`request`
interface dispatches based on ``path`` (``/track``) to the matching SDK
method.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.amplitude_config import AmplitudeConfig


class AmplitudeClient(ApiClient):
    """Async wrapper over a sync ``amplitude.Amplitude`` client."""

    def __init__(
        self,
        config: AmplitudeConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "AmplitudeClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> AmplitudeConfig | None:
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
                "AmplitudeClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "AmplitudeClient.request: path must be non-empty"
            )
        upper_method = method.upper()
        if upper_method != "POST":
            raise ValueError(
                "AmplitudeClient.request: only POST is supported; got "
                f"{method!r}"
            )
        normalised = "/" + path.lstrip("/")
        if normalised != "/track":
            raise ValueError(
                "AmplitudeClient.request: unsupported path "
                f"{path!r}; supported: /track"
            )
        request_body: dict[str, Any] = dict(body) if body is not None else {}
        if "event" not in request_body:
            raise ValueError(
                "AmplitudeClient.request(/track): body requires 'event'"
            )
        event = await self._build_event(request_body)
        client = await self._ensure_client()
        return await asyncio.to_thread(client.track, event)

    async def close(self) -> None:
        if self._client is not None:
            flush_fn = getattr(self._client, "flush", None)
            shutdown_fn = getattr(self._client, "shutdown", None)
            if callable(flush_fn):
                await asyncio.to_thread(flush_fn)
            if callable(shutdown_fn):
                await asyncio.to_thread(shutdown_fn)
            self._client = None
        self._closed = True
        self._logger.debug("amplitude.close")

    async def _build_event(self, body: Mapping[str, Any]) -> Any:
        try:
            from amplitude import BaseEvent  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AmplitudeClient requires amplitude-analytics; install via "
                "`pip install pirn[amplitude]`"
            ) from exc
        return BaseEvent(
            event_type=body["event"],
            user_id=body.get("user_id"),
            event_properties=(
                dict(body["properties"]) if body.get("properties") else None
            ),
        )

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("AmplitudeClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from amplitude import Amplitude  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "AmplitudeClient requires amplitude-analytics; install via "
                "`pip install pirn[amplitude]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "AmplitudeClient: missing config and no injected client"
            )
        if self._config.api_key is None:
            raise RuntimeError(
                "AmplitudeClient: config.api_key is required"
            )
        try:
            client = await asyncio.to_thread(Amplitude, self._config.api_key)
        except Exception as exc:
            safe_message = self._scrubber.scrub(str(exc))
            raise type(exc)(safe_message) from None
        self._logger.debug("amplitude.connect")
        return client
