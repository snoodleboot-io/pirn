"""Tests for :class:`pirn.connectors.object_storage.azure_blob_config.AzureBlobConfig`."""

from __future__ import annotations

import unittest

from pirn.connectors.object_storage.azure_blob_config import AzureBlobConfig


class TestAzureBlobConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = AzureBlobConfig()
        self.assertIsNone(cfg.account_name)
        self.assertIsNone(cfg.account_key)
        self.assertIsNone(cfg.connection_string)
        self.assertIsNone(cfg.container)
        self.assertEqual(cfg.chunk_size, 65536)

    def test_construct_with_connection_string(self) -> None:
        cfg = AzureBlobConfig(
            connection_string="DefaultEndpointsProtocol=https;AccountName=myaccount;AccountKey=mykey;",
            container="mycontainer",
        )
        self.assertEqual(cfg.container, "mycontainer")

    def test_construct_with_account_credentials(self) -> None:
        cfg = AzureBlobConfig(
            account_name="myaccount",
            account_key="base64key==",
            container="mycontainer",
        )
        self.assertEqual(cfg.account_name, "myaccount")
        self.assertEqual(cfg.container, "mycontainer")

    def test_sensitive_fields(self) -> None:
        self.assertIn("account_key", AzureBlobConfig.sensitive_fields)
        self.assertIn("connection_string", AzureBlobConfig.sensitive_fields)

    def test_repr_redacts_sensitive(self) -> None:
        cfg = AzureBlobConfig(account_key="secret-key", connection_string="conn-secret")
        text = repr(cfg)
        self.assertNotIn("secret-key", text)
        self.assertNotIn("conn-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = AzureBlobConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.container = "mutated"  # type: ignore[misc]
