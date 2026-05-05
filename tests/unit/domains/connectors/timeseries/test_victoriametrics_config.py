"""Tests for :class:`pirn.domains.connectors.timeseries.victoriametrics_config.VictoriaMetricsConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.timeseries.victoriametrics_config import VictoriaMetricsConfig


class TestVictoriaMetricsConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = VictoriaMetricsConfig()
        self.assertEqual(cfg.url, "http://localhost:8428")
        self.assertIsNone(cfg.username)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.tenant_id)
        self.assertTrue(cfg.verify_ssl)
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = VictoriaMetricsConfig(
            url="https://vm.example.com:8428",
            username="vm_user",
            password="vm-pw",
            tenant_id="0",
            verify_ssl=False,
            timeout=60.0,
        )
        self.assertEqual(cfg.url, "https://vm.example.com:8428")
        self.assertEqual(cfg.tenant_id, "0")
        self.assertFalse(cfg.verify_ssl)

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", VictoriaMetricsConfig.sensitive_fields)

    def test_repr_redacts_password(self) -> None:
        cfg = VictoriaMetricsConfig(password="vm-secret")
        text = repr(cfg)
        self.assertNotIn("vm-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = VictoriaMetricsConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.url = "mutated"  # type: ignore[misc]
