"""Telegram Bot API connector via ``httpx``.

Exposes:

1. **Vendor-typed methods**: :meth:`send_message`, :meth:`send_photo`.
2. The generic :meth:`request` escape hatch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.messaging.telegram_config import TelegramConfig


class TelegramClient(ApiClient):
    """Async Telegram Bot API client backed by ``httpx``."""

    _base_url: str = "https://api.telegram.org"

    def __init__(
        self,
        config: TelegramConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("TelegramClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> TelegramConfig | None:
        return self._config

    async def send_message(
        self,
        chat_id: str | int,
        text: str,
        *,
        parse_mode: str | None = None,
    ) -> dict:
        """Send a text message via ``sendMessage``.

        Parameters
        ----------
        chat_id:
            Target chat identifier.
        text:
            Message text.
        parse_mode:
            Override the config default parse mode.
        """
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        effective_parse_mode = parse_mode
        if effective_parse_mode is None and self._config is not None:
            effective_parse_mode = self._config.parse_mode
        if effective_parse_mode is not None:
            payload["parse_mode"] = effective_parse_mode
        self._logger.debug("telegram.send_message chat_id=%s", chat_id)
        return await self._call("sendMessage", payload)

    async def send_photo(
        self,
        chat_id: str | int,
        photo_url: str,
        *,
        caption: str | None = None,
    ) -> dict:
        """Send a photo via ``sendPhoto``.

        Parameters
        ----------
        chat_id:
            Target chat identifier.
        photo_url:
            URL of the photo to send.
        caption:
            Optional caption text.
        """
        payload: dict[str, Any] = {"chat_id": chat_id, "photo": photo_url}
        if caption is not None:
            payload["caption"] = caption
        self._logger.debug("telegram.send_photo chat_id=%s", chat_id)
        return await self._call("sendPhoto", payload)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — POSTs to Telegram API method at ``path``."""
        self._logger.debug("telegram.request path=%s", path)
        return await self._call(path, dict(body) if body is not None else {})

    async def _call(self, telegram_method: str, payload: dict) -> dict:
        client = await self._ensure_client()
        token = self._bot_token()
        url = f"{self._base_url}/bot{token}/{telegram_method}"
        response = await client.post(url, json=payload)
        return dict(response)

    def _bot_token(self) -> str:
        if self._config is not None and self._config.bot_token:
            return self._config.bot_token
        raise RuntimeError("TelegramClient: no bot_token available without config")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("telegram.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("TelegramClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "TelegramClient requires httpx; install via pip install pirn[telegram]"
            ) from exc
        if self._config is None:
            raise RuntimeError("TelegramClient: missing config and no injected client")
        if not self._config.bot_token:
            raise ValueError("TelegramClient: config.bot_token must be non-empty")
        self._logger.debug("telegram.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
