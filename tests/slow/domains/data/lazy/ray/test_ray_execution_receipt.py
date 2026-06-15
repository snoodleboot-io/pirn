"""Tests for :class:`RayExecutionReceipt`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

pytestmark = pytest.mark.slow

from pirn_data.lazy.ray.ray_execution_receipt import (
    RayExecutionReceipt,
)


class TestRayExecutionReceipt:
    def test_minimal_construction(self) -> None:
        receipt = RayExecutionReceipt(
            backend_name="ray",
            target_path=None,
        )
        assert receipt.backend_name == "ray"
        assert receipt.target_path is None
        assert receipt.dataset_size is None
        assert receipt.block_count is None

    def test_with_optional_fields(self) -> None:
        now = datetime.now(UTC)
        receipt = RayExecutionReceipt(
            backend_name="ray",
            target_path="/tmp/out",
            dataset_size=42,
            block_count=4,
            executed_at=now,
        )
        assert receipt.target_path == "/tmp/out"
        assert receipt.dataset_size == 42
        assert receipt.block_count == 4
        assert receipt.executed_at == now

    def test_receipt_is_frozen(self) -> None:
        receipt = RayExecutionReceipt(backend_name="ray", target_path=None)
        with pytest.raises(Exception):
            receipt.backend_name = "other"  # type: ignore[misc]
