"""Slack connector wrapping ``slack-sdk`` ``AsyncWebClient``.

Exposes:

1. **Vendor-typed methods**: :meth:`send_message`, :meth:`upload_file`.
2. The generic :meth:`request` escape hatch via ``client.api_call``.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.messaging.slack_config import SlackConfig


class SlackClient(ApiClient):
    """Async Slack client backed by ``slack_sdk.web.async_client.AsyncWebClient``."""

    def __init__(
        self,
        config: SlackConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("SlackClient requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> SlackConfig | None:
        return self._config

    async def send_message(
        self,
        channel: str,
        text: str,
        *,
        blocks: list | None = None,
    ) -> dict:
        """Post a message to a Slack channel via ``chat_postMessage``.

        Parameters
        ----------
        channel:
            Channel ID or name to post to.
        text:
            Message text.
        blocks:
            Optional Block Kit blocks list.
        """
        client = await self._ensure_client()
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if blocks is not None:
            kwargs["blocks"] = blocks
        self._logger.debug("slack.send_message channel=%s", channel)
        response = await client.chat_postMessage(**kwargs)
        return dict(response)

    async def upload_file(
        self,
        channel: str,
        content: bytes,
        filename: str,
    ) -> dict:
        """Upload a file to a Slack channel via ``files_upload_v2``.

        Parameters
        ----------
        channel:
            Channel ID or name.
        content:
            Raw file bytes.
        filename:
            Filename shown in Slack.
        """
        client = await self._ensure_client()
        self._logger.debug("slack.upload_file channel=%s filename=%s", channel, filename)
        response = await client.files_upload_v2(
            channel=channel,
            content=content,
            filename=filename,
        )
        return dict(response)

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Generic escape hatch — calls ``client.api_call(path, ...)``."""
        client = await self._ensure_client()
        body_dict = dict(body) if body is not None else None
        params_dict = dict(params) if params is not None else None
        self._logger.debug("slack.request path=%s", path)
        return await client.api_call(path, json=body_dict, params=params_dict)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.async_close()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("slack.close")

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("SlackClient is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from slack_sdk.web.async_client import AsyncWebClient  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "SlackClient requires slack-sdk; install via pip install pirn[slack]"
            ) from exc
        if self._config is None:
            raise RuntimeError("SlackClient: missing config and no injected client")
        if not self._config.bot_token:
            raise ValueError("SlackClient: config.bot_token must be non-empty")
        self._logger.debug("slack.connect")
        return AsyncWebClient(
            token=self._config.bot_token,
            timeout=self._config.timeout,
        )
