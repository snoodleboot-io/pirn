"""Tests for :class:`pirn.connectors.saas.mixpanel_config.MixpanelConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.mixpanel_config import MixpanelConfig


class TestMixpanelConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = MixpanelConfig()
        self.assertIsNone(cfg.project_token)
        self.assertIsNone(cfg.api_secret)
        self.assertIsNone(cfg.service_account_username)
        self.assertIsNone(cfg.service_account_secret)

    def test_construct_with_fields(self) -> None:
        cfg = MixpanelConfig(
            project_token="proj-tok",
            api_secret="api-secret",
            service_account_username="sa-user",
            service_account_secret="sa-secret",
        )
        self.assertEqual(cfg.project_token, "proj-tok")
        self.assertEqual(cfg.service_account_username, "sa-user")

    def test_sensitive_fields(self) -> None:
        self.assertIn("project_token", MixpanelConfig.sensitive_fields)
        self.assertIn("api_secret", MixpanelConfig.sensitive_fields)
        self.assertIn("service_account_secret", MixpanelConfig.sensitive_fields)

    def test_repr_redacts_sensitive(self) -> None:
        cfg = MixpanelConfig(project_token="pt-secret", api_secret="as-secret")
        text = repr(cfg)
        self.assertNotIn("pt-secret", text)
        self.assertNotIn("as-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = MixpanelConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.project_token = "mutated"  # type: ignore[misc]
