"""Tests for :class:`pirn.domains.connectors.saas.google_analytics_config.GoogleAnalyticsConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.google_analytics_config import GoogleAnalyticsConfig


class TestGoogleAnalyticsConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = GoogleAnalyticsConfig()
        self.assertIsNone(cfg.property_id)
        self.assertIsNone(cfg.service_account_json)

    def test_construct_with_fields(self) -> None:
        cfg = GoogleAnalyticsConfig(
            property_id="123456789",
            service_account_json='{"type": "service_account"}',
        )
        self.assertEqual(cfg.property_id, "123456789")

    def test_sensitive_fields(self) -> None:
        self.assertIn("service_account_json", GoogleAnalyticsConfig.sensitive_fields)

    def test_repr_redacts_service_account(self) -> None:
        cfg = GoogleAnalyticsConfig(service_account_json='{"private_key": "secret"}')
        text = repr(cfg)
        self.assertNotIn("secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = GoogleAnalyticsConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.property_id = "mutated"  # type: ignore[misc]
