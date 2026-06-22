"""Discord connector using incoming webhooks via ``httpx``.

Exposes:

1. **Vendor-typed methods**: :meth:`send_message`, :meth:`send_embed`.
2. The generic :meth:`request` escape hatch.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.messaging.discord_config import DiscordConfig


class DiscordClient(ApiClient):
    """Async Discord client that POSTs to an incoming webhook via ``httpx``."""

    def __init__(
        self,
        config: DiscordConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("DiscordClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DiscordConfig | None:
        return self._config

    async def send_message(
        self,
        content: str,
        *,
        username: str | None = None,
        embeds: list | None = None,
    ) -> dict:
        """POST a message to the Discord webhook.

        Parameters
        ----------
        content:
            Message text content.
        username:
            Override the webhook's default display name.
        embeds:
            Optional list of embed objects.
        """
        payload: dict[str, Any] = {"content": content}
        if username is not None:
            payload["username"] = username
        if embeds is not None:
            payload["embeds"] = embeds
        self._logger.debug("discord.send_message")
        return await self._post(payload)

    async def send_embed(
        self,
        title: str,
        description: str,
        *,
        color: int = 0x5865F2,
    ) -> dict:
        """POST an embed via the Discord webhook.

        Parameters
        ----------
        title:
            Embed title.
        description:
            Embed description text.
        color:
            Embed accent colour as an integer (default Discord Blurple).
        """
        payload: dict[str, Any] = {
            "embeds": [
                {
                    "title": title,
                    "description": description,
                    "color": color,
                }
            ]
        }
        self._logger.debug("discord.send_embed title=%s", title)
        return await self._post(payload)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — sends an httpx request."""
        client = await self._ensure_client()
        self._logger.debug("discord.request method=%s path=%s", method, path)
        response = await client.request(
            method,
            path,
            params=dict(params) if params is not None else None,
            json=dict(body) if body is not None else None,
            headers=dict(headers) if headers is not None else None,
        )
        return response

    async def _post(self, payload: dict) -> dict:
        client = await self._ensure_client()
        webhook_url = self._webhook_url()
        response = await client.post(webhook_url, json=payload)
        return dict(response)

    def _webhook_url(self) -> str:
        if self._config is not None and self._config.webhook_url:
            return self._config.webhook_url
        raise RuntimeError("DiscordClient: no webhook_url available")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("discord.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("DiscordClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DiscordClient requires httpx; install via pip install pirn[discord]"
            ) from exc
        if self._config is None:
            raise RuntimeError("DiscordClient: missing config and no injected client")
        if not self._config.webhook_url and not self._config.bot_token:
            raise ValueError(
                "DiscordClient: at least one of webhook_url or bot_token must be non-empty"
            )
        self._logger.debug("discord.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
