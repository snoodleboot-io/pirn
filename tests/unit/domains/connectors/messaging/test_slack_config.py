"""Tests for :class:`pirn.domains.connectors.messaging.slack_config.SlackConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.messaging.slack_config import SlackConfig


class TestSlackConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = SlackConfig()
        self.assertEqual(cfg.bot_token, "")
        self.assertIsNone(cfg.app_token)
        self.assertEqual(cfg.default_channel, "")
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = SlackConfig(
            bot_token="xoxb-abc-123",
            app_token="xapp-xyz",
            default_channel="#general",
        )
        self.assertEqual(cfg.bot_token, "xoxb-abc-123")
        self.assertEqual(cfg.default_channel, "#general")

    def test_sensitive_fields(self) -> None:
        self.assertIn("bot_token", SlackConfig.sensitive_fields)
        self.assertIn("app_token", SlackConfig.sensitive_fields)

    def test_repr_redacts_tokens(self) -> None:
        cfg = SlackConfig(bot_token="xoxb-secret", app_token="xapp-secret")
        text = repr(cfg)
        self.assertNotIn("xoxb-secret", text)
        self.assertNotIn("xapp-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = SlackConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.bot_token = "mutated"  # type: ignore[misc]
