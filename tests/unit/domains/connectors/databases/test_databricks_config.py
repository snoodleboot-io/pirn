"""Tests for :class:`pirn.domains.connectors.databases.databricks_config.DatabricksConfig`."""

from __future__ import annotations

import unittest

from pirn.domains.connectors.databases.databricks_config import DatabricksConfig


class TestDatabricksConfig(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DatabricksConfig()
        self.assertIsNone(cfg.server_hostname)
        self.assertIsNone(cfg.http_path)
        self.assertIsNone(cfg.access_token)
        self.assertIsNone(cfg.catalog)
        self.assertIsNone(cfg.schema)

    def test_construct_with_fields(self) -> None:
        cfg = DatabricksConfig(
            server_hostname="adb-1234.0.azuredatabricks.net",
            http_path="/sql/1.0/warehouses/abcd",
            access_token="dapi-secret",
            catalog="main",
            schema="default",
        )
        self.assertEqual(cfg.server_hostname, "adb-1234.0.azuredatabricks.net")
        self.assertEqual(cfg.http_path, "/sql/1.0/warehouses/abcd")
        self.assertEqual(cfg.catalog, "main")

    def test_repr_redacts_access_token(self) -> None:
        cfg = DatabricksConfig(access_token="dapi-super-secret")
        text = repr(cfg)
        self.assertNotIn("dapi-super-secret", text)
        self.assertIn("<redacted>", text)

    def test_frozen(self) -> None:
        cfg = DatabricksConfig()
        with self.assertRaises((AttributeError, TypeError)):
            cfg.server_hostname = "mutated"  # type: ignore[misc]

    def test_audit_dict_redacts_token(self) -> None:
        cfg = DatabricksConfig(access_token="tok")
        audit = cfg.to_audit_dict()
        self.assertEqual(audit["access_token"], "<redacted>")
