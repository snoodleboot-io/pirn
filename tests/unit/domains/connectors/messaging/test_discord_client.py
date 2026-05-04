"""Unit tests for :class:`DiscordClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.messaging.discord_client import DiscordClient
from pirn.domains.connectors.messaging.discord_config import DiscordConfig


# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`DiscordClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"id": "123456789"}
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    async def request(self, method: str, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.response

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance


def test_implements_api_client() -> None:
    client = DiscordClient(client=FakeHTTPXClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        DiscordClient()


def test_sensitive_fields_declared() -> None:
    cfg = DiscordConfig()
    assert "webhook_url" in cfg.sensitive_fields
    assert "bot_token" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────────── send_message


@pytest.mark.asyncio
class TestSendMessage:
    async def test_send_message_posts_to_webhook(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        result = await client.send_message("Hello Discord")
        assert result == {"id": "123456789"}
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["json"]["content"] == "Hello Discord"

    async def test_send_message_with_username(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        await client.send_message("Hi", username="BotName")
        assert fake.calls[0]["json"]["username"] == "BotName"

    async def test_send_message_with_embeds(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        embeds = [{"title": "Test", "description": "Hello"}]
        await client.send_message("Hi", embeds=embeds)
        assert fake.calls[0]["json"]["embeds"] == embeds


# ─────────────────────────────────────────────────────────────── send_embed


@pytest.mark.asyncio
class TestSendEmbed:
    async def test_send_embed_posts_embed_payload(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        await client.send_embed("Title", "Description")
        payload = fake.calls[0]["json"]
        assert len(payload["embeds"]) == 1
        assert payload["embeds"][0]["title"] == "Title"
        assert payload["embeds"][0]["description"] == "Description"

    async def test_send_embed_uses_default_color(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        await client.send_embed("T", "D")
        assert fake.calls[0]["json"]["embeds"][0]["color"] == 0x5865F2

    async def test_send_embed_custom_color(self) -> None:
        fake = FakeHTTPXClient()
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/token")
        client = DiscordClient(config=cfg, client=fake)
        await client.send_embed("T", "D", color=0xFF0000)
        assert fake.calls[0]["json"]["embeds"][0]["color"] == 0xFF0000


# ────────────────────────────────────────────────────────────── lifecycle


@pytest.mark.asyncio
class TestLifecycle:
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = DiscordClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = DiscordClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()
