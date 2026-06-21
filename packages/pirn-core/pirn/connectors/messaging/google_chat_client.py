"""Google Chat connector using incoming webhooks via ``httpx``.

Exposes:

1. **Vendor-typed methods**: :meth:`send_message`, :meth:`send_card`.
2. The generic :meth:`request` escape hatch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.messaging.google_chat_config import GoogleChatConfig


class GoogleChatClient(ApiClient):
    """Async Google Chat client that POSTs to an incoming webhook via ``httpx``."""

    def __init__(
        self,
        config: GoogleChatConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("GoogleChatClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> GoogleChatConfig | None:
        return self._config

    async def send_message(self, text: str) -> dict:
        """POST a plain text message to the Google Chat webhook.

        Parameters
        ----------
        text:
            Message text.
        """
        self._logger.debug("google_chat.send_message")
        return await self._post({"text": text})

    async def send_card(self, card: dict) -> dict:
        """POST a card payload to the Google Chat webhook.

        Parameters
        ----------
        card:
            Full Google Chat card payload.
        """
        self._logger.debug("google_chat.send_card")
        return await self._post(card)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — POSTs ``body`` to the webhook URL."""
        self._logger.debug("google_chat.request path=%s", path)
        return await self._post(dict(body) if body is not None else {})

    async def _post(self, payload: dict) -> dict:
        client = await self._ensure_client()
        webhook_url = self._webhook_url()
        response = await client.post(webhook_url, json=payload)
        return dict(response)

    def _webhook_url(self) -> str:
        if self._config is not None:
            return self._config.webhook_url
        raise RuntimeError("GoogleChatClient: no webhook_url available without config")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("google_chat.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("GoogleChatClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "GoogleChatClient requires httpx; install via pip install pirn[google-chat]"
            ) from exc
        if self._config is None:
            raise RuntimeError("GoogleChatClient: missing config and no injected client")
        if not self._config.webhook_url:
            raise ValueError("GoogleChatClient: config.webhook_url must be non-empty")
        self._logger.debug("google_chat.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
