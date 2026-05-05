"""Tests for HudiTableConfig."""

from __future__ import annotations

import unittest

from pirn.domains.data.lakehouse.hudi.hudi_table_config import HudiTableConfig


class TestHudiTableConfigConstruction(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = HudiTableConfig()
        self.assertIsNone(cfg.table_path)
        self.assertEqual(cfg.table_type, "COPY_ON_WRITE")
        self.assertEqual(cfg.record_key_field, "id")
        self.assertEqual(cfg.precombine_field, "ts")
        self.assertIsNone(cfg.partition_path_field)

    def test_custom_fields(self) -> None:
        cfg = HudiTableConfig(
            table_path="s3://my-bucket/hudi_table",
            table_type="MERGE_ON_READ",
            record_key_field="uuid",
            precombine_field="updated_at",
            partition_path_field="region",
        )
        self.assertEqual(cfg.table_path, "s3://my-bucket/hudi_table")
        self.assertEqual(cfg.table_type, "MERGE_ON_READ")
        self.assertEqual(cfg.record_key_field, "uuid")
        self.assertEqual(cfg.precombine_field, "updated_at")
        self.assertEqual(cfg.partition_path_field, "region")

    def test_frozen(self) -> None:
        cfg = HudiTableConfig(table_path="/data/tbl")
        with self.assertRaises((AttributeError, TypeError)):
            cfg.table_path = "/other"  # type: ignore[misc]

    def test_sensitive_fields_empty(self) -> None:
        self.assertEqual(HudiTableConfig.sensitive_fields, ())

    def test_repr_does_not_raise(self) -> None:
        cfg = HudiTableConfig(table_path="/data/tbl")
        r = repr(cfg)
        self.assertIsInstance(r, str)
