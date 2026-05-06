"""Unit tests for :class:`GoogleChatClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.messaging.google_chat_client import GoogleChatClient
from pirn.domains.connectors.messaging.google_chat_config import GoogleChatConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`GoogleChatClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"name": "spaces/AAAAA/messages/12345"}
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = GoogleChatClient(client=FakeHTTPXClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            GoogleChatClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = GoogleChatConfig()
        assert "webhook_url" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── send_message


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_posts_text(self) -> None:
        fake = FakeHTTPXClient()
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=abc")
        client = GoogleChatClient(config=cfg, client=fake)
        result = await client.send_message("Hello Google Chat")
        assert result == {"name": "spaces/AAAAA/messages/12345"}
        assert fake.calls[0]["json"] == {"text": "Hello Google Chat"}

    async def test_send_message_posts_to_webhook_url(self) -> None:
        fake = FakeHTTPXClient()
        webhook = "https://chat.googleapis.com/v1/spaces/123/messages?key=abc"
        cfg = GoogleChatConfig(webhook_url=webhook)
        client = GoogleChatClient(config=cfg, client=fake)
        await client.send_message("Hi")
        assert fake.calls[0]["url"] == webhook


# ─────────────────────────────────────────────────────────────── send_card


class TestSendCard(unittest.IsolatedAsyncioTestCase):
    async def test_send_card_posts_payload(self) -> None:
        fake = FakeHTTPXClient()
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=abc")
        client = GoogleChatClient(config=cfg, client=fake)
        card = {"cards": [{"header": {"title": "Test"}}]}
        await client.send_card(card)
        assert fake.calls[0]["json"] == card


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = GoogleChatClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = GoogleChatClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_webhook_url(self) -> None:
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=supersecret")
        text = repr(cfg)
        assert "supersecret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_webhook_url(self) -> None:
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=supersecret")
        d = cfg.to_audit_dict()
        assert d["webhook_url"] == "<redacted>"
        assert "supersecret" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = GoogleChatClient(
            config=GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=tok"),
            client=FakeHTTPXClient(),
        )
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = GoogleChatClient(
            config=GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/123/messages?key=tok"),
            client=FakeHTTPXClient(),
        )
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.send_message("Hello")
