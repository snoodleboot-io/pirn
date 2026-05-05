"""Tests for :class:`IbisExecutionReceipt`."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pirn.domains.data.lazy.ibis.ibis_execution_receipt import IbisExecutionReceipt


class TestIbisExecutionReceipt(unittest.TestCase):
    def test_construction_defaults(self) -> None:
        receipt = IbisExecutionReceipt(
            backend_name="duckdb",
            target_table=None,
            compiled_sql="SELECT 1",
        )
        self.assertEqual(receipt.backend_name, "duckdb")
        self.assertIsNone(receipt.target_table)
        self.assertEqual(receipt.compiled_sql, "SELECT 1")
        self.assertIsNone(receipt.row_count)

    def test_construction_with_all_fields(self) -> None:
        now = datetime.now(timezone.utc)
        receipt = IbisExecutionReceipt(
            backend_name="sqlite",
            target_table="output_table",
            compiled_sql="SELECT id FROM users",
            row_count=42,
            executed_at=now,
        )
        self.assertEqual(receipt.row_count, 42)
        self.assertEqual(receipt.target_table, "output_table")
        self.assertEqual(receipt.executed_at, now)

    def test_frozen_dataclass(self) -> None:
        receipt = IbisExecutionReceipt(
            backend_name="duckdb",
            target_table=None,
            compiled_sql="SELECT 1",
        )
        with self.assertRaises((AttributeError, TypeError)):
            receipt.backend_name = "other"  # type: ignore[misc]
