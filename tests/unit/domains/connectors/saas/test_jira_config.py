"""Tests for :class:`pirn.domains.connectors.saas.jira_config.JiraConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.saas.jira_config import JiraConfig


class TestJiraConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = JiraConfig()
        self.assertIsNone(cfg.url)
        self.assertIsNone(cfg.username)
        self.assertIsNone(cfg.api_token)
        self.assertTrue(cfg.cloud)

    def test_construct_with_fields(self) -> None:
        cfg = JiraConfig(
            url="https://acme.atlassian.net",
            username="user@acme.com",
            api_token="jira-api-token",
            cloud=True,
        )
        self.assertEqual(cfg.url, "https://acme.atlassian.net")
        self.assertEqual(cfg.username, "user@acme.com")

    def test_on_premise(self) -> None:
        cfg = JiraConfig(url="https://jira.internal.com", cloud=False)
        self.assertFalse(cfg.cloud)

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_token", JiraConfig.sensitive_fields)

    def test_repr_redacts_api_token(self) -> None:
        cfg = JiraConfig(api_token="jira-secret")
        text = repr(cfg)
        self.assertNotIn("jira-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = JiraConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.url = "mutated"  # type: ignore[misc]
