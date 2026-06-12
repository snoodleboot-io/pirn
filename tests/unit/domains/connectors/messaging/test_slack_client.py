"""Unit tests for :class:`SlackClient`.

Uses an injected stub client mirroring the ``slack_sdk`` ``AsyncWebClient`` interface.
No real Slack account or network needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.api_client import ApiClient
from pirn.connectors.messaging.slack_client import SlackClient
from pirn.connectors.messaging.slack_config import SlackConfig

# ──────────────────────────────────────────────────────────── fake client


class FakeSlackClient:
    """Mirrors the slice of ``AsyncWebClient`` used by :class:`SlackClient`."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.response: dict[str, Any] = {"ok": True}
        self.closed = False

    async def chat_postMessage(self, **kwargs: Any) -> dict:
        self.calls.append({"method": "chat_postMessage", **kwargs})
        return self.response

    async def files_upload_v2(self, **kwargs: Any) -> dict:
        self.calls.append({"method": "files_upload_v2", **kwargs})
        return self.response

    async def api_call(self, path: str, **kwargs: Any) -> dict:
        self.calls.append({"method": "api_call", "path": path, **kwargs})
        return self.response

    async def async_close(self) -> None:
        self.closed = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_api_client(self) -> None:
        client = SlackClient(client=FakeSlackClient())
        assert isinstance(client, ApiClient)
    
    
    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            SlackClient()
    
    
    def test_sensitive_fields_declared(self) -> None:
        cfg = SlackConfig()
        assert "bot_token" in cfg.sensitive_fields
        assert "app_token" in cfg.sensitive_fields
    
    
# ────────────────────────────────────────────────────────────── send_message


class TestSendMessage(unittest.IsolatedAsyncioTestCase):
    async def test_send_message_calls_chat_post_message(self) -> None:
        fake = FakeSlackClient()
        client = SlackClient(client=fake)
        result = await client.send_message("#general", "Hello")
        assert result == {"ok": True}
        assert len(fake.calls) == 1
        assert fake.calls[0]["method"] == "chat_postMessage"
        assert fake.calls[0]["channel"] == "#general"
        assert fake.calls[0]["text"] == "Hello"

    async def test_send_message_with_blocks(self) -> None:
        fake = FakeSlackClient()
        client = SlackClient(client=fake)
        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello"}}]
        await client.send_message("#general", "Hello", blocks=blocks)
        assert fake.calls[0]["blocks"] == blocks

    async def test_send_message_without_blocks_omits_key(self) -> None:
        fake = FakeSlackClient()
        client = SlackClient(client=fake)
        await client.send_message("#general", "Hello")
        assert "blocks" not in fake.calls[0]


# ─────────────────────────────────────────────────────────────── upload_file


class TestUploadFile(unittest.IsolatedAsyncioTestCase):
    async def test_upload_file_calls_files_upload_v2(self) -> None:
        fake = FakeSlackClient()
        client = SlackClient(client=fake)
        result = await client.upload_file("#general", b"data", "report.csv")
        assert result == {"ok": True}
        assert fake.calls[0]["method"] == "files_upload_v2"
        assert fake.calls[0]["channel"] == "#general"
        assert fake.calls[0]["content"] == b"data"
        assert fake.calls[0]["filename"] == "report.csv"


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_calls_async_close(self) -> None:
        fake = FakeSlackClient()
        client = SlackClient(client=fake)
        await client.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        client = SlackClient(client=FakeSlackClient())
        await client.close()
        await client.close()

    async def test_request_after_close_raises(self) -> None:
        client = SlackClient(client=FakeSlackClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.request("GET", "chat.postMessage")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_bot_token(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-secret-token")
        text = repr(cfg)
        assert "xoxb-secret-token" not in text
        assert "<redacted>" in text

    def test_repr_redacts_app_token(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-t", app_token="xapp-secret")
        text = repr(cfg)
        assert "xapp-secret" not in text

    def test_audit_dict_redacts_bot_token(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-supersecret")
        d = cfg.to_audit_dict()
        assert d["bot_token"] == "<redacted>"
        assert "xoxb-supersecret" not in str(d)


class TestSecurity(unittest.IsolatedAsyncioTestCase):
    async def test_close_clears_credentials(self) -> None:
        client = SlackClient(config=SlackConfig(bot_token="xoxb-tok"), client=FakeSlackClient())
        assert client._config is not None
        await client.close()
        assert client._config is None

    async def test_use_after_close_raises(self) -> None:
        client = SlackClient(config=SlackConfig(bot_token="xoxb-tok"), client=FakeSlackClient())
        await client.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await client.send_message("#general", "Hello")
