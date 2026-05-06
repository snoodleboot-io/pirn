"""Amplitude Analytics ingestion connector wrapping the sync ``Amplitude`` SDK.

The official ``amplitude-analytics`` SDK is synchronous and
ingestion-only; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop.

The connector exposes:

1. **Vendor-typed methods** — :meth:`track`.
2. The :class:`EventEmitter` capability — :meth:`emit` accepts
   ``{"user_id", "event"|"event_type", "properties"?}`` and forwards to
   :meth:`track`.
3. The legacy :meth:`request` escape hatch (``POST /track``).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.event_emitter import EventEmitter
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.amplitude_config import AmplitudeConfig


class AmplitudeClient(ApiClient, EventEmitter):
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

    async def emit(self, event: Mapping[str, Any]) -> None:
        """:class:`EventEmitter` adapter — forwards to :meth:`track`.

        ``event`` requires a ``user_id`` and an event-name key
        (``event_type`` preferred, ``event`` accepted as a synonym).
        ``properties`` is optional.
        """
        if "user_id" not in event:
            raise ValueError(
                "AmplitudeClient.emit: event requires 'user_id'"
            )
        event_type = event.get("event_type")
        if event_type is None:
            event_type = event.get("event")
        if event_type is None:
            raise ValueError(
                "AmplitudeClient.emit: event requires 'event_type' or 'event'"
            )
        await self.track(
            user_id=event["user_id"],
            event_type=event_type,
            properties=event.get("properties"),
        )

    async def track(
        self,
        *,
        user_id: str,
        event_type: str,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        """Vendor-typed wrapper around ``Amplitude.track``."""
        if not isinstance(user_id, str) or not user_id:
            raise ValueError(
                "AmplitudeClient.track: user_id must be a non-empty string"
            )
        if not isinstance(event_type, str) or not event_type:
            raise ValueError(
                "AmplitudeClient.track: event_type must be a non-empty string"
            )
        amplitude_event = await self._build_event(
            {
                "event": event_type,
                "user_id": user_id,
                "properties": (
                    dict(properties) if properties is not None else None
                ),
            }
        )
        client = await self._ensure_client()
        await asyncio.to_thread(client.track, amplitude_event)

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
        self._clear_credentials()
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
            self._reraise_scrubbed(exc)
        self._logger.debug("amplitude.connect")
        return client
