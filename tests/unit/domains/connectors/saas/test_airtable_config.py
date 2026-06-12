"""Tests for :class:`pirn.connectors.saas.airtable_config.AirtableConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.saas.airtable_config import AirtableConfig


class TestAirtableConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AirtableConfig()
        self.assertEqual(cfg.api_key, "")
        self.assertEqual(cfg.base_id, "")
        self.assertEqual(cfg.table_name, "")
        self.assertEqual(cfg.page_size, 100)
        self.assertEqual(cfg.timeout, 30.0)

    def test_construct_with_fields(self) -> None:
        cfg = AirtableConfig(
            api_key="patXXXXXXX",
            base_id="appXXXXXXXX",
            table_name="Projects",
            page_size=50,
        )
        self.assertEqual(cfg.api_key, "patXXXXXXX")
        self.assertEqual(cfg.base_id, "appXXXXXXXX")
        self.assertEqual(cfg.page_size, 50)

    def test_sensitive_fields(self) -> None:
        self.assertIn("api_key", AirtableConfig.sensitive_fields)

    def test_repr_redacts_api_key(self) -> None:
        cfg = AirtableConfig(api_key="pat-secret")
        text = repr(cfg)
        self.assertNotIn("pat-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AirtableConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.base_id = "mutated"  # type: ignore[misc]
