"""Tests for :class:`pirn.domains.connectors.saas.zendesk_config.ZendeskConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.zendesk_config import ZendeskConfig


class TestZendeskConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = ZendeskConfig()
        self.assertIsNone(cfg.subdomain)
        self.assertIsNone(cfg.email)
        self.assertIsNone(cfg.api_token)
        self.assertIsNone(cfg.oauth_token)

    def test_construct_with_token_auth(self) -> None:
        cfg = ZendeskConfig(
            subdomain="acme",
            email="agent@acme.com",
            api_token="zd-api-token",
        )
        self.assertEqual(cfg.subdomain, "acme")
        self.assertEqual(cfg.email, "agent@acme.com")

    def test_construct_with_oauth(self) -> None:
        cfg = ZendeskConfig(subdomain="acme", oauth_token="oauth-tok")
        self.assertEqual(cfg.oauth_token, "oauth-tok")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_token", ZendeskConfig.sensitive_fields)
        self.assertIn("oauth_token", ZendeskConfig.sensitive_fields)

    def test_repr_redacts_tokens(self) -> None:
        cfg = ZendeskConfig(api_token="api-secret", oauth_token="oauth-secret")
        text = repr(cfg)
        self.assertNotIn("api-secret", text)
        self.assertNotIn("oauth-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = ZendeskConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.subdomain = "mutated"  # type: ignore[misc]
