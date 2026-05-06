"""Tests for :class:`pirn.domains.connectors.messaging.teams_config.TeamsConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.messaging.teams_config import TeamsConfig


class TestTeamsConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = TeamsConfig()
        self.assertEqual(cfg.webhook_url, "")
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_webhook(self) -> None:
        cfg = TeamsConfig(webhook_url="https://outlook.office.com/webhook/abc/123")
        self.assertEqual(cfg.webhook_url, "https://outlook.office.com/webhook/abc/123")

    def test_sensitive_fields(self) -> None:
        self.assertIn("webhook_url", TeamsConfig.sensitive_fields)

    def test_repr_redacts_webhook(self) -> None:
        cfg = TeamsConfig(webhook_url="https://teams-webhook/secret")
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = TeamsConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.timeout = 99.0  # type: ignore[misc]
