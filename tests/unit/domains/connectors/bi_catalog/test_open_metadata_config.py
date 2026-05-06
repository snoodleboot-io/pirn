"""Tests for :class:`pirn.domains.connectors.bi_catalog.open_metadata_config.OpenMetadataConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.bi_catalog.open_metadata_config import OpenMetadataConfig


class TestOpenMetadataConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = OpenMetadataConfig()
        self.assertIsNone(cfg.host_url)
        self.assertIsNone(cfg.jwt_token)

    def test_construct_with_fields(self) -> None:
        cfg = OpenMetadataConfig(
            host_url="https://open-metadata.acme.com/api",
            jwt_token="jwt.abc.xyz",
        )
        self.assertEqual(cfg.host_url, "https://open-metadata.acme.com/api")
        self.assertEqual(cfg.jwt_token, "jwt.abc.xyz")

    def test_sensitive_fields(self) -> None:
        self.assertIn("jwt_token", OpenMetadataConfig.sensitive_fields)

    def test_repr_redacts_jwt(self) -> None:
        cfg = OpenMetadataConfig(jwt_token="secret-jwt")
        text = repr(cfg)
        self.assertNotIn("secret-jwt", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = OpenMetadataConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.host_url = "mutated"  # type: ignore[misc]

    def test_audit_dict(self) -> None:
        cfg = OpenMetadataConfig(jwt_token="tok")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["jwt_token"], "<redacted>")
