"""Tests for :class:`pirn.domains.connectors.streaming.pubsub_config.PubSubConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.streaming.pubsub_config import PubSubConfig


class TestPubSubConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = PubSubConfig()
        self.assertIsNone(cfg.project)
        self.assertIsNone(cfg.service_account_json)

    def test_construct_with_fields(self) -> None:
        cfg = PubSubConfig(project="my-gcp-project", service_account_json="/keys/sa.json")
        self.assertEqual(cfg.project, "my-gcp-project")

    def test_sensitive_fields(self) -> None:
        self.assertIn("service_account_json", PubSubConfig.sensitive_fields)

    def test_repr_redacts_service_account_json(self) -> None:
        cfg = PubSubConfig(service_account_json="/path/to/secret.json")
        text = repr(cfg)
        self.assertNotIn("/path/to/secret.json", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = PubSubConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.project = "mutated"  # type: ignore[misc]
