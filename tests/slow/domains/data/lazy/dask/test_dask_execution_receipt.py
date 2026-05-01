"""Tests for :class:`DaskExecutionReceipt`."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.slow

from pirn.domains.data.lazy.dask.dask_execution_receipt import (
    DaskExecutionReceipt,
)


class TestDaskExecutionReceipt:
    def test_minimal_construction(self) -> None:
        receipt = DaskExecutionReceipt(
            backend_name="dask",
            target_path=None,
            partitions_executed=4,
        )
        assert receipt.backend_name == "dask"
        assert receipt.target_path is None
        assert receipt.partitions_executed == 4
        assert receipt.row_count is None

    def test_with_optional_fields(self) -> None:
        now = datetime.now(timezone.utc)
        receipt = DaskExecutionReceipt(
            backend_name="dask",
            target_path="/tmp/out.parquet",
            partitions_executed=2,
            row_count=100,
            executed_at=now,
        )
        assert receipt.target_path == "/tmp/out.parquet"
        assert receipt.row_count == 100
        assert receipt.executed_at == now

    def test_receipt_is_frozen(self) -> None:
        receipt = DaskExecutionReceipt(
            backend_name="dask", target_path=None, partitions_executed=1,
        )
        with pytest.raises(Exception):
            receipt.backend_name = "other"  # type: ignore[misc]
