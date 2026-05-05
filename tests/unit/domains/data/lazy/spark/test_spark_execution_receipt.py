"""Tests for :class:`SparkExecutionReceipt`."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pirn.domains.data.lazy.spark.spark_execution_receipt import SparkExecutionReceipt


class TestSparkExecutionReceipt(unittest.TestCase):
    def test_construction_with_output_path(self) -> None:
        now = datetime.now(timezone.utc)
        receipt = SparkExecutionReceipt(
            succeeded=True,
            row_count=None,
            output_path="s3://bucket/out",
            completed_at=now,
        )
        self.assertTrue(receipt.succeeded)
        self.assertIsNone(receipt.row_count)
        self.assertEqual(receipt.output_path, "s3://bucket/out")
        self.assertEqual(receipt.completed_at, now)

    def test_construction_with_row_count(self) -> None:
        receipt = SparkExecutionReceipt(
            succeeded=True,
            row_count=500,
            output_path=None,
        )
        self.assertEqual(receipt.row_count, 500)
        self.assertIsNone(receipt.output_path)

    def test_audit_dict_keys(self) -> None:
        receipt = SparkExecutionReceipt(succeeded=False, row_count=0, output_path=None)
        d = receipt._pirn_audit_dict()
        self.assertIn("succeeded", d)
        self.assertIn("row_count", d)
        self.assertIn("output_path", d)
        self.assertIn("completed_at", d)

    def test_frozen(self) -> None:
        receipt = SparkExecutionReceipt(succeeded=True, row_count=None, output_path=None)
        with self.assertRaises((AttributeError, TypeError)):
            receipt.succeeded = False  # type: ignore[misc]
