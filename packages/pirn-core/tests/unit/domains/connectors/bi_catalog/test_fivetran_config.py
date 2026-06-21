"""Tests for :class:`pirn.connectors.bi_catalog.fivetran_config.FivetranConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.bi_catalog.fivetran_config import FivetranConfig


class TestFivetranConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = FivetranConfig()
        self.assertIsNone(cfg.api_key)
        self.assertIsNone(cfg.api_secret)
        self.assertEqual(cfg.base_url, "https://api.fivetran.com/v1")

    def test_construct_with_all_fields(self) -> None:
        cfg = FivetranConfig(
            api_key="key123",
            api_secret="secret456",
            base_url="https://custom.fivetran.com/v1",
        )
        self.assertEqual(cfg.api_key, "key123")
        self.assertEqual(cfg.api_secret, "secret456")
        self.assertEqual(cfg.base_url, "https://custom.fivetran.com/v1")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", FivetranConfig.sensitive_fields)
        self.assertIn("api_secret", FivetranConfig.sensitive_fields)

    def test_repr_redacts_credentials(self) -> None:
        cfg = FivetranConfig(api_key="mykey", api_secret="mysecret")
        text = repr(cfg)
        self.assertNotIn("mykey", text)
        self.assertNotIn("mysecret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = FivetranConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.api_key = "mutated"  # type: ignore[misc]

    def test_audit_dict(self) -> None:
        cfg = FivetranConfig(api_key="k", api_secret="s")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["api_key"], "<redacted>")
        self.assertEqual(audit["api_secret"], "<redacted>")
        self.assertEqual(audit["base_url"], "https://api.fivetran.com/v1")
