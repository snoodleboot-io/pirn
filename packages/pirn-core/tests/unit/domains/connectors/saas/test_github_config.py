"""Tests for :class:`pirn.connectors.saas.github_config.GitHubConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.github_config import GitHubConfig


class TestGitHubConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = GitHubConfig()
        self.assertIsNone(cfg.token)
        self.assertEqual(cfg.base_url, "https://api.github.com")
        self.assertIsNone(cfg.app_id)
        self.assertIsNone(cfg.private_key)

    def test_construct_with_token(self) -> None:
        cfg = GitHubConfig(token="ghp_my-token")
        self.assertEqual(cfg.token, "ghp_my-token")

    def test_construct_with_app_credentials(self) -> None:
        cfg = GitHubConfig(app_id="12345", private_key="-----BEGIN RSA PRIVATE KEY-----")
        self.assertEqual(cfg.app_id, "12345")

    def test_sensitive_fields(self) -> None:
        self.assertIn("token", GitHubConfig.sensitive_fields)
        self.assertIn("private_key", GitHubConfig.sensitive_fields)

    def test_repr_redacts_sensitive(self) -> None:
        cfg = GitHubConfig(token="ghp-secret", private_key="pem-secret")
        text = repr(cfg)
        self.assertNotIn("ghp-secret", text)
        self.assertNotIn("pem-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = GitHubConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.token = "mutated"  # type: ignore[misc]
