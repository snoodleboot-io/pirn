"""Tests for :class:`DaskExecutionReceipt`."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pirn.domains.data.lazy.dask.dask_execution_receipt import DaskExecutionReceipt


class TestDaskExecutionReceipt(unittest.TestCase):
    def test_construction_with_target_path(self) -> None:
        now = datetime.now(timezone.utc)
        receipt = DaskExecutionReceipt(
            backend_name="dask",
            target_path="s3://bucket/out",
            partitions_executed=4,
            row_count=None,
            executed_at=now,
        )
        self.assertEqual(receipt.backend_name, "dask")
        self.assertEqual(receipt.target_path, "s3://bucket/out")
        self.assertEqual(receipt.partitions_executed, 4)
        self.assertIsNone(receipt.row_count)

    def test_construction_with_row_count(self) -> None:
        receipt = DaskExecutionReceipt(
            backend_name="dask",
            target_path=None,
            partitions_executed=2,
            row_count=100,
        )
        self.assertEqual(receipt.row_count, 100)
        self.assertIsNone(receipt.target_path)

    def test_frozen_dataclass(self) -> None:
        receipt = DaskExecutionReceipt(
            backend_name="dask",
            target_path=None,
            partitions_executed=1,
        )
        with self.assertRaises((AttributeError, TypeError)):
            receipt.backend_name = "other"  # type: ignore[misc]
