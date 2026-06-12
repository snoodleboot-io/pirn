"""Microsoft Teams connector using incoming webhooks via ``httpx``.

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
from pirn.connectors.messaging.teams_config import TeamsConfig


class TeamsClient(ApiClient):
    """Async Teams client that POSTs Adaptive Cards to an incoming webhook."""

    def __init__(
        self,
        config: TeamsConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("TeamsClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> TeamsConfig | None:
        return self._config

    async def send_message(
        self,
        text: str,
        *,
        title: str | None = None,
        color: str = "0076D7",
    ) -> dict:
        """Send a simple Adaptive Card message to the webhook.

        Parameters
        ----------
        text:
            Message body text.
        title:
            Optional card title.
        color:
            Accent colour hex string (without ``#``).
        """
        body: dict[str, Any] = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {"type": "TextBlock", "text": text, "wrap": True},
                        ],
                        "msteams": {"accentColor": color},
                    },
                }
            ],
        }
        if title is not None:
            body["attachments"][0]["content"]["body"].insert(
                0, {"type": "TextBlock", "text": title, "weight": "Bolder", "size": "Medium"}
            )
        self._logger.debug("teams.send_message")
        return await self._post(body)

    async def send_card(self, card: dict) -> dict:
        """POST an arbitrary Adaptive Card payload to the webhook.

        Parameters
        ----------
        card:
            Full Adaptive Card message payload.
        """
        self._logger.debug("teams.send_card")
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
        self._logger.debug("teams.request path=%s", path)
        return await self._post(dict(body) if body is not None else {})

    async def _post(self, payload: dict) -> dict:
        client = await self._ensure_client()
        webhook_url = self._webhook_url()
        response = await client.post(webhook_url, json=payload)
        return dict(response)

    def _webhook_url(self) -> str:
        if self._config is not None:
            return self._config.webhook_url
        raise RuntimeError("TeamsClient: no webhook_url available without config")

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("teams.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("TeamsClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import httpx  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "TeamsClient requires httpx; install via pip install pirn[teams]"
            ) from exc
        if self._config is None:
            raise RuntimeError("TeamsClient: missing config and no injected client")
        if not self._config.webhook_url:
            raise ValueError("TeamsClient: config.webhook_url must be non-empty")
        self._logger.debug("teams.connect")
        return httpx.AsyncClient(timeout=self._config.timeout)
