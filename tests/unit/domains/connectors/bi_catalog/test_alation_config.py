"""Tests for :class:`pirn.connectors.bi_catalog.alation_config.AlationConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.bi_catalog.alation_config import AlationConfig


class TestAlationConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AlationConfig()
        self.assertIsNone(cfg.base_url)
        self.assertIsNone(cfg.refresh_token)
        self.assertIsNone(cfg.user_id)

    def test_construct_with_all_fields(self) -> None:
        cfg = AlationConfig(
            base_url="https://alation.acme.com",
            refresh_token="rt-xyz",
            user_id=42,
        )
        self.assertEqual(cfg.base_url, "https://alation.acme.com")
        self.assertEqual(cfg.refresh_token, "rt-xyz")
        self.assertEqual(cfg.user_id, 42)

    def test_sensitive_fields(self) -> None:
        self.assertIn("refresh_token", AlationConfig.sensitive_fields)

    def test_repr_redacts_refresh_token(self) -> None:
        cfg = AlationConfig(refresh_token="secret-refresh")
        text = repr(cfg)
        self.assertNotIn("secret-refresh", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AlationConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.base_url = "mutated"  # type: ignore[misc]

    def test_audit_dict_redacts_refresh_token(self) -> None:
        cfg = AlationConfig(refresh_token="rt-secret")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["refresh_token"], "<redacted>")
        self.assertIsNone(audit["base_url"])
