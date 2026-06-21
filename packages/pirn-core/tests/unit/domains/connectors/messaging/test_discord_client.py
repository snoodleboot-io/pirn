"""Unit tests for :class:`DiscordClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.messaging.discord_client import DiscordClient
from pirn.connectors.messaging.discord_config import DiscordConfig

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



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = DiscordClient(client=FakeHTTPXClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            DiscordClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = DiscordConfig()
        assert "webhook_url" in cfg.sensitive_fields
        assert "bot_token" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── send_message


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
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


class TestSendEmbed(unittest.IsolatedAsyncioTestCase):
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


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = DiscordClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = DiscordClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_webhook_url(self) -> None:
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/supersecret")
        text = repr(cfg)
        assert "supersecret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_webhook_url(self) -> None:
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/supersecret")
        d = cfg.to_audit_dict()
        assert d["webhook_url"] == "<redacted>"
        assert "supersecret" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = DiscordClient(
            config=DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/tok"),
            client=FakeHTTPXClient(),
        )
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = DiscordClient(
            config=DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/tok"),
            client=FakeHTTPXClient(),
        )
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.send_message("Hello")
