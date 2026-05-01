"""Tests for :class:`pirn.domains.data.quality.row_count_gate.RowCountGate`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality.row_count_gate import RowCountGate
from pirn.domains.data.quality_report import QualityReport
from pirn.tapestry import Tapestry


def _batch_factory(row_count: int):
    @knot
    async def emit() -> DataBatch:
        rows = tuple({"id": i} for i in range(row_count))
        return DataBatch(rows=rows)
    return emit


@pytest.mark.asyncio
class TestRowCountGate:
    async def test_passes_when_within_bounds(self) -> None:
        with Tapestry() as t:
            batch = _batch_factory(50)(_config=KnotConfig(id="batch"))
            RowCountGate(
                batch=batch, min_rows=10, max_rows=100,
                _config=KnotConfig(id="count"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["count"]
        assert report.passed is True
        assert report.row_count == 50

    async def test_fails_below_min(self) -> None:
        with Tapestry() as t:
            batch = _batch_factory(2)(_config=KnotConfig(id="batch"))
            RowCountGate(
                batch=batch, min_rows=10, _config=KnotConfig(id="count"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["count"]
        assert report.passed is False
        assert any(c.name == "row_count_min" for c in report.failed_checks)

    async def test_fails_above_max(self) -> None:
        with Tapestry() as t:
            batch = _batch_factory(200)(_config=KnotConfig(id="batch"))
            RowCountGate(
                batch=batch, min_rows=0, max_rows=100,
                _config=KnotConfig(id="count"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["count"]
        assert report.passed is False
        assert any(c.name == "row_count_max" for c in report.failed_checks)

    async def test_max_unset_means_no_upper_bound(self) -> None:
        with Tapestry() as t:
            batch = _batch_factory(10_000)(_config=KnotConfig(id="batch"))
            RowCountGate(
                batch=batch, min_rows=1, _config=KnotConfig(id="count"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["count"]
        assert report.passed is True


class TestRowCountGateConstruction:
    def test_rejects_negative_min(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="min_rows"):
                RowCountGate(batch=batch, min_rows=-1, _config=KnotConfig(id="c"))

    def test_rejects_max_less_than_min(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with pytest.raises(ValueError, match="max_rows"):
                RowCountGate(
                    batch=batch, min_rows=10, max_rows=5,
                    _config=KnotConfig(id="c"),
                )
