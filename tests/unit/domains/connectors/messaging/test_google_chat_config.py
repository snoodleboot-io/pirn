"""Tests for :class:`pirn.domains.connectors.messaging.google_chat_config.GoogleChatConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.messaging.google_chat_config import GoogleChatConfig


class TestGoogleChatConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = GoogleChatConfig()
        self.assertEqual(cfg.webhook_url, "")
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_webhook(self) -> None:
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/v1/spaces/abc/messages?key=xyz")
        self.assertEqual(cfg.webhook_url, "https://chat.googleapis.com/v1/spaces/abc/messages?key=xyz")

    def test_sensitive_fields(self) -> None:
        self.assertIn("webhook_url", GoogleChatConfig.sensitive_fields)

    def test_repr_redacts_webhook(self) -> None:
        cfg = GoogleChatConfig(webhook_url="https://chat.googleapis.com/secret")
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = GoogleChatConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.timeout = 99.0  # type: ignore[misc]
