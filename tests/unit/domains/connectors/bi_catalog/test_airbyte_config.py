"""Tests for :class:`pirn.domains.connectors.bi_catalog.airbyte_config.AirbyteConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.bi_catalog.airbyte_config import AirbyteConfig


class TestAirbyteConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AirbyteConfig()
        self.assertEqual(cfg.base_url, "https://api.airbyte.com/v1")
        self.assertIsNone(cfg.client_id)
        self.assertIsNone(cfg.client_secret)
        self.assertIsNone(cfg.access_token)

    def test_construct_with_all_fields(self) -> None:
        cfg = AirbyteConfig(
            base_url="https://custom.airbyte.com/v1",
            client_id="my-client-id",
            client_secret="my-secret",
            access_token="tok-abc",
        )
        self.assertEqual(cfg.base_url, "https://custom.airbyte.com/v1")
        self.assertEqual(cfg.client_id, "my-client-id")
        self.assertEqual(cfg.client_secret, "my-secret")
        self.assertEqual(cfg.access_token, "tok-abc")

    def test_sensitive_fields(self) -> None:
        self.assertIn("client_secret", AirbyteConfig.sensitive_fields)
        self.assertIn("access_token", AirbyteConfig.sensitive_fields)

    def test_repr_redacts_sensitive_fields(self) -> None:
        cfg = AirbyteConfig(client_secret="super-secret", access_token="tok-xyz")
        text = repr(cfg)
        self.assertNotIn("super-secret", text)
        self.assertNotIn("tok-xyz", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AirbyteConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.base_url = "mutated"  # type: ignore[misc]

    def test_audit_dict_redacts(self) -> None:
        cfg = AirbyteConfig(client_secret="s3cr3t", access_token="tok")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["client_secret"], "<redacted>")
        self.assertEqual(audit["access_token"], "<redacted>")
        self.assertEqual(audit["base_url"], "https://api.airbyte.com/v1")
