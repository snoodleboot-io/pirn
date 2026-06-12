"""Tests for :class:`pirn.connectors.saas.twilio_config.TwilioConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.twilio_config import TwilioConfig


class TestTwilioConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = TwilioConfig()
        self.assertIsNone(cfg.account_sid)
        self.assertIsNone(cfg.auth_token)
        self.assertIsNone(cfg.region)

    def test_construct_with_fields(self) -> None:
        cfg = TwilioConfig(
            account_sid="ACxxxxxxxx",
            auth_token="auth-secret",
            region="au1",
        )
        self.assertEqual(cfg.account_sid, "ACxxxxxxxx")
        self.assertEqual(cfg.region, "au1")

    def test_sensitive_fields(self) -> None:
        self.assertIn("auth_token", TwilioConfig.sensitive_fields)

    def test_repr_redacts_auth_token(self) -> None:
        cfg = TwilioConfig(auth_token="twilio-secret")
        text = repr(cfg)
        self.assertNotIn("twilio-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = TwilioConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.account_sid = "mutated"  # type: ignore[misc]
