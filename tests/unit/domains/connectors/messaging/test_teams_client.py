"""Unit tests for :class:`TeamsClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.messaging.teams_client import TeamsClient
from pirn.connectors.messaging.teams_config import TeamsConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`TeamsClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"ok": True}
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = TeamsClient(client=FakeHTTPXClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            TeamsClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = TeamsConfig()
        assert "webhook_url" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── send_message


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_posts_adaptive_card(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TeamsConfig(webhook_url="https://hook.example.com/webhook")
        client = TeamsClient(config=cfg, client=fake)
        result = await client.send_message("Hello Teams")
        assert result == {"ok": True}
        assert len(fake.calls) == 1
        assert fake.calls[0]["method"] == "POST"
        assert fake.calls[0]["url"] == "https://hook.example.com/webhook"

    async def test_send_message_with_title(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TeamsConfig(webhook_url="https://hook.example.com/webhook")
        client = TeamsClient(config=cfg, client=fake)
        await client.send_message("Body text", title="My Title")
        payload = fake.calls[0]["json"]
        card_body = payload["attachments"][0]["content"]["body"]
        assert any(b.get("text") == "My Title" for b in card_body)


# ─────────────────────────────────────────────────────────────── send_card


class TestSendCard(unittest.IsolatedAsyncioTestCase):
    async def test_send_card_posts_payload(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TeamsConfig(webhook_url="https://hook.example.com/webhook")
        client = TeamsClient(config=cfg, client=fake)
        card = {"type": "message", "text": "custom"}
        await client.send_card(card)
        assert fake.calls[0]["json"] == card


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = TeamsClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = TeamsClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_webhook_url(self) -> None:
        cfg = TeamsConfig(webhook_url="https://hook.example.com/supersecret")
        text = repr(cfg)
        assert "supersecret" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_webhook_url(self) -> None:
        cfg = TeamsConfig(webhook_url="https://hook.example.com/supersecret")
        d = cfg.to_audit_dict()
        assert d["webhook_url"] == "<redacted>"
        assert "supersecret" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = TeamsClient(
            config=TeamsConfig(webhook_url="https://hook.example.com/tok"),
            client=FakeHTTPXClient(),
        )
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = TeamsClient(
            config=TeamsConfig(webhook_url="https://hook.example.com/tok"),
            client=FakeHTTPXClient(),
        )
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.send_message("Hello")
