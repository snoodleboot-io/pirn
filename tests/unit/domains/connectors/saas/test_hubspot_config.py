"""Tests for :class:`pirn.connectors.saas.hubspot_config.HubSpotConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.hubspot_config import HubSpotConfig


class TestHubSpotConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = HubSpotConfig()
        self.assertIsNone(cfg.access_token)
        self.assertIsNone(cfg.api_key)

    def test_construct_with_access_token(self) -> None:
        cfg = HubSpotConfig(access_token="pat-na1-secret")
        self.assertEqual(cfg.access_token, "pat-na1-secret")

    def test_sensitive_fields(self) -> None:
        self.assertIn("access_token", HubSpotConfig.sensitive_fields)
        self.assertIn("api_key", HubSpotConfig.sensitive_fields)

    def test_repr_redacts_credentials(self) -> None:
        cfg = HubSpotConfig(access_token="tok-secret", api_key="key-secret")
        text = repr(cfg)
        self.assertNotIn("tok-secret", text)
        self.assertNotIn("key-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = HubSpotConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.access_token = "mutated"  # type: ignore[misc]
