"""Tests for :class:`RayExecutionReceipt`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

import pytest
from pirn_data.lazy.ray.ray_execution_receipt import RayExecutionReceipt

pytestmark = pytest.mark.slow


class TestRayExecutionReceipt(unittest.TestCase):
    def test_construction_defaults(self) -> None:
        receipt = RayExecutionReceipt(
            backend_name="ray",
            target_path=None,
        )
        self.assertEqual(receipt.backend_name, "ray")
        self.assertIsNone(receipt.target_path)
        self.assertIsNone(receipt.dataset_size)
        self.assertIsNone(receipt.block_count)

    def test_construction_with_all_fields(self) -> None:
        now = datetime.now(UTC)
        receipt = RayExecutionReceipt(
            backend_name="ray",
            target_path="s3://bucket/out",
            dataset_size=1000,
            block_count=5,
            executed_at=now,
        )
        self.assertEqual(receipt.dataset_size, 1000)
        self.assertEqual(receipt.block_count, 5)
        self.assertEqual(receipt.executed_at, now)

    def test_frozen(self) -> None:
        receipt = RayExecutionReceipt(backend_name="ray", target_path=None)
        with self.assertRaises((AttributeError, TypeError)):
            receipt.backend_name = "other"  # type: ignore[misc]
