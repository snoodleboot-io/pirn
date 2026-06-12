"""Tests for :class:`pirn.connectors.bi_catalog.datahub_config.DataHubConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.bi_catalog.datahub_config import DataHubConfig


class TestDataHubConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DataHubConfig()
        self.assertIsNone(cfg.gms_url)
        self.assertIsNone(cfg.token)

    def test_construct_with_fields(self) -> None:
        cfg = DataHubConfig(gms_url="http://datahub:8080", token="my-token")
        self.assertEqual(cfg.gms_url, "http://datahub:8080")
        self.assertEqual(cfg.token, "my-token")

    def test_sensitive_fields(self) -> None:
        self.assertIn("token", DataHubConfig.sensitive_fields)

    def test_repr_redacts_token(self) -> None:
        cfg = DataHubConfig(token="secret-bearer")
        text = repr(cfg)
        self.assertNotIn("secret-bearer", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = DataHubConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.gms_url = "mutated"  # type: ignore[misc]

    def test_audit_dict(self) -> None:
        cfg = DataHubConfig(gms_url="http://host", token="tok")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["token"], "<redacted>")
        self.assertEqual(audit["gms_url"], "http://host")
