"""Unit tests for :class:`TelegramClient`.

Uses an injected stub httpx client. No network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.messaging.telegram_client import TelegramClient
from pirn.domains.connectors.messaging.telegram_config import TelegramConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeHTTPXClient:
    """Minimal httpx.AsyncClient stub for :class:`TelegramClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"ok": True, "result": {"message_id": 1}}
        self.closed = False

    async def post(self, url: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "POST", "url": url, **kwargs})
        return self.response

    async def aclose(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = TelegramClient(client=FakeHTTPXClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            TelegramClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = TelegramConfig(bot_token="123:ABC")
        assert "bot_token" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── parse_mode validation


class TestParseModeValidation(unittest.TestCase):
    def test_valid_html_parse_mode(self) -> None:
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="HTML")
        assert cfg.parse_mode == "HTML"

    def test_valid_markdown_parse_mode(self) -> None:
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="Markdown")
        assert cfg.parse_mode == "Markdown"

    def test_valid_markdownv2_parse_mode(self) -> None:
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="MarkdownV2")
        assert cfg.parse_mode == "MarkdownV2"

    def test_invalid_parse_mode_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "parse_mode"):
            TelegramConfig(bot_token="123:ABC", parse_mode="invalid")


# ────────────────────────────────────────────────────────────── send_message


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_posts_to_correct_url(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TelegramConfig(bot_token="123456:ABCDEF")
        client = TelegramClient(config=cfg, client=fake)
        result = await client.send_message("42", "Hello")
        assert result == {"ok": True, "result": {"message_id": 1}}
        assert "123456:ABCDEF" in fake.calls[0]["url"]
        assert "sendMessage" in fake.calls[0]["url"]
        assert fake.calls[0]["json"]["chat_id"] == "42"
        assert fake.calls[0]["json"]["text"] == "Hello"

    async def test_send_message_includes_config_parse_mode(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="HTML")
        client = TelegramClient(config=cfg, client=fake)
        await client.send_message("42", "<b>Hello</b>")
        assert fake.calls[0]["json"]["parse_mode"] == "HTML"

    async def test_send_message_override_parse_mode(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TelegramConfig(bot_token="123:ABC", parse_mode="HTML")
        client = TelegramClient(config=cfg, client=fake)
        await client.send_message("42", "**Hello**", parse_mode="Markdown")
        assert fake.calls[0]["json"]["parse_mode"] == "Markdown"

    async def test_send_message_with_integer_chat_id(self) -> None:
        fake = FakeHTTPXClient()
        cfg = TelegramConfig(bot_token="123:ABC")
        client = TelegramClient(config=cfg, client=fake)
        await client.send_message(-1001234567890, "Hello group")
        assert fake.calls[0]["json"]["chat_id"] == -1001234567890


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_aclose(self) -> None:
        fake = FakeHTTPXClient()
        client = TelegramClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = TelegramClient(client=FakeHTTPXClient())
        await client.close()
        await client.close()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_bot_token(self) -> None:
        cfg = TelegramConfig(bot_token="123456:ABCDEF-SECRET")
        text = repr(cfg)
        assert "ABCDEF-SECRET" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_bot_token(self) -> None:
        cfg = TelegramConfig(bot_token="123456:SUPERSECRET")
        d = cfg.to_audit_dict()
        assert d["bot_token"] == "<redacted>"
        assert "SUPERSECRET" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = TelegramClient(
            config=TelegramConfig(bot_token="123456:ABCDEF"),
            client=FakeHTTPXClient(),
        )
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = TelegramClient(
            config=TelegramConfig(bot_token="123456:ABCDEF"),
            client=FakeHTTPXClient(),
        )
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.send_message("42", "Hello")
