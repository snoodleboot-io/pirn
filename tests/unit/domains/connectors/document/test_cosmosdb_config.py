"""Tests for :class:`pirn.domains.connectors.document.cosmosdb_config.CosmosDBConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.document.cosmosdb_config import CosmosDBConfig


class TestCosmosDBConfig(unittest.TestCase):
    def test_construct_with_endpoint(self) -> None:
        cfg = CosmosDBConfig(
            endpoint="https://myaccount.documents.azure.com:443/",
            key="base64key==",
            database="mydb",
            container="items",
        )
        self.assertEqual(cfg.endpoint, "https://myaccount.documents.azure.com:443/")
        self.assertEqual(cfg.database, "mydb")

    def test_defaults(self) -> None:
        cfg = CosmosDBConfig(endpoint="https://myaccount.documents.azure.com/")
        self.assertEqual(cfg.connection_mode, "gateway")
        self.assertEqual(cfg.max_retry_attempts, 3)

    def test_empty_endpoint_raises(self) -> None:
        with self.assertRaises(ValueError):
            CosmosDBConfig(endpoint="")

    def test_sensitive_fields(self) -> None:
        self.assertIn("key", CosmosDBConfig.sensitive_fields)

    def test_repr_redacts_key(self) -> None:
        cfg = CosmosDBConfig(endpoint="https://acc.documents.azure.com/", key="secret-key")
        text = repr(cfg)
        self.assertNotIn("secret-key", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = CosmosDBConfig(endpoint="https://acc.documents.azure.com/")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.endpoint = "mutated"  # type: ignore[misc]
