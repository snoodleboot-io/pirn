"""Mixpanel ingestion connector wrapping the sync ``mixpanel.Mixpanel`` SDK.

The official ``mixpanel`` SDK is synchronous and ingestion-only; calls
run in a worker thread via :func:`asyncio.to_thread`. The connector
exposes:

1. The :class:`EventEmitter` capability — :meth:`emit` accepts a
   single Mixpanel-shaped event (``{"distinct_id", "event", "properties"}``)
   and forwards it to ``Mixpanel.track``.
2. The vendor-typed :meth:`track` and :meth:`import_data` methods.
3. The legacy :meth:`request` escape hatch with ``method="POST"`` and
   ``path="/track"`` or ``"/import"``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.capabilities.event_emitter import EventEmitter
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.saas.mixpanel_config import MixpanelConfig


class MixpanelClient(ApiClient, EventEmitter):
    """Async wrapper over a sync ``mixpanel.Mixpanel`` client."""

    def __init__(
        self,
        config: MixpanelConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError(
                "MixpanelClient requires either config= or client="
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> MixpanelConfig | None:
        return self._config

    async def emit(self, event: Mapping[str, Any]) -> None:
        """:class:`EventEmitter` adapter — forwards to :meth:`track`.

        ``event`` requires keys ``distinct_id`` and ``event``;
        ``properties`` is optional.
        """
        if "distinct_id" not in event or "event" not in event:
            raise ValueError(
                "MixpanelClient.emit: event requires 'distinct_id' and "
                "'event' keys"
            )
        await self.track(
            distinct_id=event["distinct_id"],
            event_name=event["event"],
            properties=event.get("properties"),
        )

    async def track(
        self,
        *,
        distinct_id: str,
        event_name: str,
        properties: Mapping[str, Any] | None = None,
    ) -> None:
        """Vendor-typed wrapper around ``Mixpanel.track``."""
        client = await self._ensure_client()
        properties_arg: dict[str, Any] = (
            dict(properties) if properties is not None else {}
        )
        await asyncio.to_thread(
            client.track, distinct_id, event_name, properties_arg
        )

    async def import_data(self, **payload: Any) -> Any:
        """Vendor-typed wrapper around ``Mixpanel.import_data``."""
        client = await self._ensure_client()
        return await asyncio.to_thread(client.import_data, **payload)

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
                "MixpanelClient.request: method must be non-empty"
            )
        if not isinstance(path, str) or not path:
            raise ValueError(
                "MixpanelClient.request: path must be non-empty"
            )
        upper_method = method.upper()
        if upper_method != "POST":
            raise ValueError(
                "MixpanelClient.request: only POST is supported; got "
                f"{method!r}"
            )
        normalised = "/" + path.lstrip("/")
        if normalised not in ("/track", "/import"):
            raise ValueError(
                "MixpanelClient.request: unsupported path "
                f"{path!r}; supported: /track, /import"
            )
        request_body: dict[str, Any] = dict(body) if body is not None else {}
        client = await self._ensure_client()

        if normalised == "/track":
            return await asyncio.to_thread(
                self._invoke_track, client, request_body
            )
        return await asyncio.to_thread(
            self._invoke_import, client, request_body
        )

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._closed = True
        self._logger.debug("mixpanel.close")

    @staticmethod
    def _invoke_track(client: Any, body: Mapping[str, Any]) -> Any:
        if "distinct_id" not in body or "event" not in body:
            raise ValueError(
                "MixpanelClient.request(/track): body requires "
                "'distinct_id' and 'event'"
            )
        properties = body.get("properties")
        properties_arg: dict[str, Any] = (
            dict(properties) if properties is not None else {}
        )
        return client.track(
            body["distinct_id"], body["event"], properties_arg
        )

    @staticmethod
    def _invoke_import(client: Any, body: Mapping[str, Any]) -> Any:
        return client.import_data(**dict(body))

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("MixpanelClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from mixpanel import Mixpanel  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MixpanelClient requires mixpanel; install via "
                "`pip install pirn[mixpanel]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "MixpanelClient: missing config and no injected client"
            )
        if self._config.project_token is None:
            raise RuntimeError(
                "MixpanelClient: config.project_token is required"
            )
        try:
            client = await asyncio.to_thread(
                Mixpanel, self._config.project_token
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("mixpanel.connect")
        return client
