"""Tests for :class:`SparkExecutionReceipt`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import TypeAdapter

pytestmark = pytest.mark.slow

from pirn_data.lazy.spark.spark_execution_receipt import (
    SparkExecutionReceipt,
)


class TestSparkExecutionReceipt:
    def test_minimal_construction(self) -> None:
        receipt = SparkExecutionReceipt(
            succeeded=True,
            row_count=None,
            output_path=None,
        )
        assert receipt.succeeded is True
        assert receipt.row_count is None
        assert receipt.output_path is None

    def test_with_optional_fields(self) -> None:
        now = datetime.now(UTC)
        receipt = SparkExecutionReceipt(
            succeeded=True,
            row_count=42,
            output_path="/tmp/out",
            completed_at=now,
        )
        assert receipt.row_count == 42
        assert receipt.output_path == "/tmp/out"
        assert receipt.completed_at == now

    def test_receipt_is_frozen(self) -> None:
        receipt = SparkExecutionReceipt(
            succeeded=True, row_count=None, output_path=None,
        )
        with pytest.raises(Exception):
            receipt.succeeded = False  # type: ignore[misc]

    def test_pydantic_serialises_to_primitive_dict(self) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        receipt = SparkExecutionReceipt(
            succeeded=True,
            row_count=3,
            output_path="/tmp/out",
            completed_at=now,
        )
        adapter = TypeAdapter(SparkExecutionReceipt)
        # Round-trip via pydantic should produce a flat primitive dict.
        dumped = adapter.dump_python(receipt)
        assert dumped == {
            "succeeded": True,
            "row_count": 3,
            "output_path": "/tmp/out",
            "completed_at": "2026-01-01T00:00:00+00:00",
        }

    def test_pydantic_validates_via_isinstance(self) -> None:
        receipt = SparkExecutionReceipt(
            succeeded=True, row_count=None, output_path=None,
        )
        adapter = TypeAdapter(SparkExecutionReceipt)
        assert adapter.validate_python(receipt) is receipt
