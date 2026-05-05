"""Tests for DataBatch."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema


class TestDataBatchConstruction(unittest.TestCase):
    def test_empty_batch(self) -> None:
        b = DataBatch()
        self.assertEqual(b.rows, ())
        self.assertEqual(b.row_count, 0)
        self.assertEqual(b.source_uri, "")
        self.assertIsInstance(b.fetched_at, datetime)

    def test_with_rows(self) -> None:
        rows = ({"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"})
        b = DataBatch(rows=rows)
        self.assertEqual(b.row_count, 2)

    def test_with_schema(self) -> None:
        schema = DataSchema(columns={"id": int})
        b = DataBatch(schema=schema)
        self.assertEqual(b.schema.columns["id"], int)

    def test_source_uri(self) -> None:
        b = DataBatch(source_uri="s3://my-bucket/data.parquet")
        self.assertEqual(b.source_uri, "s3://my-bucket/data.parquet")

    def test_immutable(self) -> None:
        b = DataBatch()
        with self.assertRaises((AttributeError, TypeError)):
            b.source_uri = "new_value"  # type: ignore[misc]


class TestDataBatchWithRows(unittest.TestCase):
    def test_with_rows_returns_new_batch(self) -> None:
        schema = DataSchema(columns={"x": int})
        b = DataBatch(schema=schema, source_uri="db://src")
        new_rows = ({"x": 42},)
        b2 = b.with_rows(new_rows)
        self.assertEqual(b2.rows, new_rows)
        self.assertIs(b2.schema, schema)
        self.assertEqual(b2.source_uri, "db://src")

    def test_with_schema_returns_new_batch(self) -> None:
        rows = ({"x": 1},)
        b = DataBatch(rows=rows)
        new_schema = DataSchema(columns={"x": int})
        b2 = b.with_schema(new_schema)
        self.assertEqual(b2.rows, rows)
        self.assertIs(b2.schema, new_schema)


class TestDataBatchAuditDict(unittest.TestCase):
    def test_audit_dict_keys(self) -> None:
        b = DataBatch(
            rows=({"a": 1},),
            source_uri="file:///tmp/data.csv",
        )
        d = b._pirn_audit_dict()
        self.assertIn("row_count", d)
        self.assertIn("source_uri", d)
        self.assertIn("fetched_at", d)
        self.assertIn("rows", d)
        self.assertEqual(d["row_count"], 1)

    def test_canonical_includes_schema_columns(self) -> None:
        schema = DataSchema(columns={"x": int, "y": str})
        b = DataBatch(rows=({"x": 1, "y": "a"},), schema=schema)
        c = b.__pirn_canonical__()
        self.assertIn("schema_columns", c)
        self.assertEqual(c["schema_columns"], {"x": "int", "y": "str"})
