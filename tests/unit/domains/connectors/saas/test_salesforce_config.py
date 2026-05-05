"""Tests for :class:`pirn.domains.connectors.saas.salesforce_config.SalesforceConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.salesforce_config import SalesforceConfig


class TestSalesforceConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = SalesforceConfig()
        self.assertIsNone(cfg.username)
        self.assertIsNone(cfg.password)
        self.assertIsNone(cfg.security_token)
        self.assertEqual(cfg.domain, "login")
        self.assertIsNone(cfg.consumer_key)
        self.assertIsNone(cfg.consumer_secret)

    def test_construct_with_fields(self) -> None:
        cfg = SalesforceConfig(
            username="user@acme.com",
            password="sf-pw",
            security_token="sf-token",
            domain="test",
        )
        self.assertEqual(cfg.username, "user@acme.com")
        self.assertEqual(cfg.domain, "test")

    def test_sensitive_fields(self) -> None:
        self.assertIn("password", SalesforceConfig.sensitive_fields)
        self.assertIn("security_token", SalesforceConfig.sensitive_fields)
        self.assertIn("consumer_secret", SalesforceConfig.sensitive_fields)

    def test_repr_redacts_sensitive(self) -> None:
        cfg = SalesforceConfig(password="sf-secret", security_token="st-secret")
        text = repr(cfg)
        self.assertNotIn("sf-secret", text)
        self.assertNotIn("st-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = SalesforceConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.username = "mutated"  # type: ignore[misc]
