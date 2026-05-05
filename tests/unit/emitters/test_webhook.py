"""Unit tests for WebhookEmitter."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from pirn.emitters.webhook import WebhookEmitter


def _make_event() -> MagicMock:
    e = MagicMock()
    e.model_dump_json = MagicMock(return_value='{"event":"test"}')
    return e


class TestWebhookEmitterConstruction(unittest.TestCase):
    def test_rejects_invalid_scheme(self) -> None:
        with self.assertRaisesRegex(ValueError, "scheme"):
            WebhookEmitter(url_status="ftp://example.com/events")

    def test_accepts_https_url(self) -> None:
        emitter = WebhookEmitter(url_status="https://example.com/hook")
        self.assertIsNotNone(emitter)

    def test_accepts_http_url(self) -> None:
        emitter = WebhookEmitter(url_status="http://example.com/hook")
        self.assertIsNotNone(emitter)

    def test_no_urls_constructs_fine(self) -> None:
        emitter = WebhookEmitter()
        self.assertIsNotNone(emitter)

    def test_block_private_ips_rejects_loopback(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            WebhookEmitter(url_status="http://127.0.0.1/hook", block_private_ips=True)

    def test_block_private_ips_rejects_private_network(self) -> None:
        with self.assertRaisesRegex(ValueError, "private"):
            WebhookEmitter(url_status="http://192.168.1.1/hook", block_private_ips=True)

    def test_injected_client_used(self) -> None:
        client = MagicMock()
        emitter = WebhookEmitter(client=client, url_status="https://example.com")
        self.assertIs(emitter._client, client)


class TestWebhookEmitterEvents(unittest.IsolatedAsyncioTestCase):
    def _make_emitter_with_client(self) -> tuple[WebhookEmitter, MagicMock]:
        client = MagicMock()
        client.post = AsyncMock()
        emitter = WebhookEmitter(
            client=client,
            url_status="https://example.com/status",
            url_lineage="https://example.com/lineage",
            url_result="https://example.com/result",
        )
        return emitter, client

    async def test_on_status_posts(self) -> None:
        emitter, client = self._make_emitter_with_client()
        await emitter.on_status(_make_event())
        client.post.assert_called_once()

    async def test_on_lineage_posts(self) -> None:
        emitter, client = self._make_emitter_with_client()
        await emitter.on_lineage(_make_event())
        client.post.assert_called_once()

    async def test_on_run_result_posts(self) -> None:
        emitter, client = self._make_emitter_with_client()
        await emitter.on_run_result(_make_event())
        client.post.assert_called_once()

    async def test_on_status_skipped_when_no_url(self) -> None:
        client = MagicMock()
        client.post = AsyncMock()
        emitter = WebhookEmitter(client=client)
        await emitter.on_status(_make_event())
        client.post.assert_not_called()

    async def test_close_calls_aclose(self) -> None:
        client = MagicMock()
        client.aclose = AsyncMock()
        emitter = WebhookEmitter(client=client)
        await emitter.close()
        client.aclose.assert_called_once()

    async def test_close_no_client_is_noop(self) -> None:
        emitter = WebhookEmitter()
        await emitter.close()
