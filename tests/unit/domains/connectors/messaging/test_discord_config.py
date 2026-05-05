"""Tests for :class:`pirn.domains.connectors.messaging.discord_config.DiscordConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.messaging.discord_config import DiscordConfig


class TestDiscordConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DiscordConfig()
        self.assertEqual(cfg.webhook_url, "")
        self.assertIsNone(cfg.bot_token)
        self.assertIsNone(cfg.default_channel_id)
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_webhook(self) -> None:
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/123/abc")
        self.assertEqual(cfg.webhook_url, "https://discord.com/api/webhooks/123/abc")

    def test_construct_with_bot_token(self) -> None:
        cfg = DiscordConfig(bot_token="Bot my-bot-token", default_channel_id="12345")
        self.assertEqual(cfg.bot_token, "Bot my-bot-token")
        self.assertEqual(cfg.default_channel_id, "12345")

    def test_sensitive_fields(self) -> None:
        self.assertIn("webhook_url", DiscordConfig.sensitive_fields)
        self.assertIn("bot_token", DiscordConfig.sensitive_fields)

    def test_repr_redacts_webhook_url(self) -> None:
        cfg = DiscordConfig(webhook_url="https://discord.com/api/webhooks/secret")
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = DiscordConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.timeout = 99.0  # type: ignore[misc]
