"""Tests for DeltaTableConfig."""

from __future__ import annotations

import unittest

from pirn.domains.data.lakehouse.delta.delta_table_config import DeltaTableConfig


class TestDeltaTableConfigConstruction(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = DeltaTableConfig()
        self.assertIsNone(cfg.table_uri)
        self.assertEqual(cfg.storage_options, {})

    def test_with_table_uri(self) -> None:
        cfg = DeltaTableConfig(table_uri="s3://my-bucket/db/table")
        self.assertEqual(cfg.table_uri, "s3://my-bucket/db/table")

    def test_with_storage_options(self) -> None:
        cfg = DeltaTableConfig(
            table_uri="file:///data/tbl",
            storage_options={"AWS_ACCESS_KEY_ID": "AKID", "AWS_SECRET_ACCESS_KEY": "sec"},
        )
        self.assertEqual(cfg.storage_options["AWS_ACCESS_KEY_ID"], "AKID")

    def test_frozen(self) -> None:
        cfg = DeltaTableConfig(table_uri="s3://bucket/tbl")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.table_uri = "s3://other"  # type: ignore[misc]

    def test_sensitive_fields_empty(self) -> None:
        self.assertEqual(DeltaTableConfig.sensitive_fields, ())

    def test_repr_does_not_raise(self) -> None:
        cfg = DeltaTableConfig(table_uri="s3://bucket/tbl")
        r = repr(cfg)
        self.assertIsInstance(r, str)
