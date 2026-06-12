"""Tests for :class:`pirn.connectors.saas.amplitude_config.AmplitudeConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.amplitude_config import AmplitudeConfig


class TestAmplitudeConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AmplitudeConfig()
        self.assertIsNone(cfg.api_key)
        self.assertIsNone(cfg.secret_key)

    def test_construct_with_fields(self) -> None:
        cfg = AmplitudeConfig(api_key="amp-key", secret_key="amp-secret")
        self.assertEqual(cfg.api_key, "amp-key")
        self.assertEqual(cfg.secret_key, "amp-secret")

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", AmplitudeConfig.sensitive_fields)
        self.assertIn("secret_key", AmplitudeConfig.sensitive_fields)

    def test_repr_redacts_credentials(self) -> None:
        cfg = AmplitudeConfig(api_key="key-secret", secret_key="sk-secret")
        text = repr(cfg)
        self.assertNotIn("key-secret", text)
        self.assertNotIn("sk-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AmplitudeConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.api_key = "mutated"  # type: ignore[misc]
