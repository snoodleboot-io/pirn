"""Tests for :class:`pirn.domains.connectors.messaging.pagerduty_config.PagerDutyConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.messaging.pagerduty_config import PagerDutyConfig


class TestPagerDutyConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PagerDutyConfig()
        self.assertEqual(cfg.api_key, "")
        self.assertIsNone(cfg.routing_key)
        self.assertEqual(cfg.base_url, "https://api.pagerduty.com")
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = PagerDutyConfig(
            api_key="pd-api-key",
            routing_key="pd-routing-key",
            timeout=60.0,
        )
        self.assertEqual(cfg.api_key, "pd-api-key")
        self.assertEqual(cfg.routing_key, "pd-routing-key")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", PagerDutyConfig.sensitive_fields)
        self.assertIn("routing_key", PagerDutyConfig.sensitive_fields)

    def test_repr_redacts_sensitive(self) -> None:
        cfg = PagerDutyConfig(api_key="pd-secret", routing_key="rk-secret")
        text = repr(cfg)
        self.assertNotIn("pd-secret", text)
        self.assertNotIn("rk-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = PagerDutyConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.api_key = "mutated"  # type: ignore[misc]
