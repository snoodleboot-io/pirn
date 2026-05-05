"""Tests for :class:`pirn.domains.connectors.saas.stripe_config.StripeConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.stripe_config import StripeConfig


class TestStripeConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = StripeConfig()
        self.assertIsNone(cfg.api_key)
        self.assertIsNone(cfg.api_version)

    def test_construct_with_fields(self) -> None:
        cfg = StripeConfig(api_key="sk_live_secret", api_version="2024-09-30.acacia")
        self.assertEqual(cfg.api_key, "sk_live_secret")
        self.assertEqual(cfg.api_version, "2024-09-30.acacia")

    def test_test_key(self) -> None:
        cfg = StripeConfig(api_key="sk_test_secret")
        self.assertEqual(cfg.api_key, "sk_test_secret")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", StripeConfig.sensitive_fields)

    def test_repr_redacts_api_key(self) -> None:
        cfg = StripeConfig(api_key="sk_live_verysecret")
        text = repr(cfg)
        self.assertNotIn("sk_live_verysecret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = StripeConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.api_key = "mutated"  # type: ignore[misc]
