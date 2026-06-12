"""Tests for :class:`pirn.connectors.observability.grafana_config.GrafanaConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.observability.grafana_config import GrafanaConfig


class TestGrafanaConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = GrafanaConfig()
        self.assertIsNone(cfg.base_url)
        self.assertIsNone(cfg.api_key)

    def test_construct_with_fields(self) -> None:
        cfg = GrafanaConfig(
            base_url="https://grafana.example.com",
            api_key="glsa_secret_token",
        )
        self.assertEqual(cfg.base_url, "https://grafana.example.com")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", GrafanaConfig.sensitive_fields)

    def test_repr_redacts_api_key(self) -> None:
        cfg = GrafanaConfig(api_key="glsa-secret")
        text = repr(cfg)
        self.assertNotIn("glsa-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = GrafanaConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.base_url = "mutated"  # type: ignore[misc]
