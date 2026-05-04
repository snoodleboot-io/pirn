"""Unit tests for :class:`SlackClient`.

Uses an injected stub client mirroring the ``slack_sdk`` ``AsyncWebClient`` interface.
No real Slack account or network needed.
"""

from __future__ import annotations

from typing import Any

import pytest

from pirn.domains.connectors.api_client import ApiClient
from pirn.domains.connectors.messaging.slack_client import SlackClient
from pirn.domains.connectors.messaging.slack_config import SlackConfig


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


def test_implements_api_client() -> None:
    client = SlackClient(client=FakeSlackClient())
    assert isinstance(client, ApiClient)


def test_construction_requires_config_or_client() -> None:
    with pytest.raises(TypeError, match="config= or client="):
        SlackClient()


def test_sensitive_fields_declared() -> None:
    cfg = SlackConfig()
    assert "bot_token" in cfg.sensitive_fields
    assert "app_token" in cfg.sensitive_fields


# ────────────────────────────────────────────────────────────── send_message


@pytest.mark.asyncio
class TestSendMessage:
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


@pytest.mark.asyncio
class TestUploadFile:
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


@pytest.mark.asyncio
class TestLifecycle:
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
        with pytest.raises(RuntimeError, match="closed"):
            await client.request("GET", "chat.postMessage")


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety:
    def test_repr_redacts_bot_token(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-secret-token")
        text = repr(cfg)
        assert "xoxb-secret-token" not in text
        assert "<redacted>" in text

    def test_repr_redacts_app_token(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-t", app_token="xapp-secret")
        text = repr(cfg)
        assert "xapp-secret" not in text
