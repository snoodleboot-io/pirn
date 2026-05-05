"""Tests for :class:`pirn.domains.connectors.observability.prometheus_config.PrometheusConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.observability.prometheus_config import PrometheusConfig


class TestPrometheusConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PrometheusConfig()
        self.assertIsNone(cfg.base_url)
        self.assertIsNone(cfg.bearer_token)

    def test_construct_with_fields(self) -> None:
        cfg = PrometheusConfig(
            base_url="http://prometheus:9090",
            bearer_token="my-prom-token",
        )
        self.assertEqual(cfg.base_url, "http://prometheus:9090")

    def test_sensitive_fields(self) -> None:
        self.assertIn("bearer_token", PrometheusConfig.sensitive_fields)

    def test_repr_redacts_bearer_token(self) -> None:
        cfg = PrometheusConfig(bearer_token="prom-secret")
        text = repr(cfg)
        self.assertNotIn("prom-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = PrometheusConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.base_url = "mutated"  # type: ignore[misc]
