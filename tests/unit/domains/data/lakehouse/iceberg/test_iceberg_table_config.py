"""Tests for IcebergTableConfig."""

from __future__ import annotations

import unittest

from pirn_data.lakehouse.iceberg.iceberg_table_config import IcebergTableConfig


class TestIcebergTableConfigConstruction(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = IcebergTableConfig()
        self.assertIsNone(cfg.catalog_name)
        self.assertEqual(cfg.catalog_properties, {})
        self.assertIsNone(cfg.table_identifier)
        self.assertIsNone(cfg.namespace)

    def test_with_all_fields(self) -> None:
        cfg = IcebergTableConfig(
            catalog_name="glue",
            catalog_properties={"region": "us-east-1"},
            table_identifier="db.events",
            namespace="db",
        )
        self.assertEqual(cfg.catalog_name, "glue")
        self.assertEqual(cfg.catalog_properties["region"], "us-east-1")
        self.assertEqual(cfg.table_identifier, "db.events")
        self.assertEqual(cfg.namespace, "db")

    def test_rest_catalog(self) -> None:
        cfg = IcebergTableConfig(
            catalog_name="rest",
            catalog_properties={"uri": "https://catalog.example.com"},
            table_identifier="ns.table",
        )
        self.assertEqual(cfg.catalog_properties["uri"], "https://catalog.example.com")

    def test_frozen(self) -> None:
        cfg = IcebergTableConfig(catalog_name="rest")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.catalog_name = "glue"  # type: ignore[misc]

    def test_sensitive_fields_empty(self) -> None:
        self.assertEqual(IcebergTableConfig.sensitive_fields, ())

    def test_repr_does_not_raise(self) -> None:
        cfg = IcebergTableConfig(catalog_name="rest")
        r = repr(cfg)
        self.assertIsInstance(r, str)
