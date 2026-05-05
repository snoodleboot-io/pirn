"""Tests for :class:`pirn.domains.connectors.observability.datadog_config.DatadogConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.observability.datadog_config import DatadogConfig


class TestDatadogConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DatadogConfig()
        self.assertIsNone(cfg.api_key)
        self.assertIsNone(cfg.app_key)
        self.assertEqual(cfg.site, "datadoghq.com")

    def test_construct_with_fields(self) -> None:
        cfg = DatadogConfig(
            api_key="dd-api-key-123",
            app_key="dd-app-key-456",
            site="datadoghq.eu",
        )
        self.assertEqual(cfg.api_key, "dd-api-key-123")
        self.assertEqual(cfg.site, "datadoghq.eu")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", DatadogConfig.sensitive_fields)
        self.assertIn("app_key", DatadogConfig.sensitive_fields)

    def test_repr_redacts_keys(self) -> None:
        cfg = DatadogConfig(api_key="secret-api", app_key="secret-app")
        text = repr(cfg)
        self.assertNotIn("secret-api", text)
        self.assertNotIn("secret-app", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = DatadogConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.site = "mutated"  # type: ignore[misc]
