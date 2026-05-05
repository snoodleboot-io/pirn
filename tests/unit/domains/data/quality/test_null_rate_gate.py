"""Tests for :class:`pirn.domains.data.quality.null_rate_gate.NullRateGate`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality.null_rate_gate import NullRateGate
from pirn.domains.data.quality_report import QualityReport
from pirn.tapestry import Tapestry


@knot
async def emit_mostly_filled() -> DataBatch:
    rows = tuple(
        {"id": i, "email": f"u{i}@x" if i % 5 != 0 else None}
        for i in range(10)
    )
    return DataBatch(rows=rows)


@knot
async def emit_all_null_email() -> DataBatch:
    rows = tuple({"id": i, "email": None} for i in range(5))
    return DataBatch(rows=rows)


@knot
async def emit_empty() -> DataBatch:
    return DataBatch(rows=())


class TestNullRateGate(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_under_threshold(self) -> None:
        # 2 nulls in 10 rows = 0.2; threshold 0.3 → pass
        with Tapestry() as t:
            batch = emit_mostly_filled(_config=KnotConfig(id="batch"))
            NullRateGate(
                batch=batch,
                thresholds={"email": 0.3},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is True
        assert report.checks[0].column == "email"
        assert report.checks[0].actual == "0.2000"

    async def test_fails_when_above_threshold(self) -> None:
        # 2 nulls in 10 rows = 0.2; threshold 0.1 → fail
        with Tapestry() as t:
            batch = emit_mostly_filled(_config=KnotConfig(id="batch"))
            NullRateGate(
                batch=batch,
                thresholds={"email": 0.1},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is False

    async def test_fails_when_all_nulls_against_zero_threshold(self) -> None:
        with Tapestry() as t:
            batch = emit_all_null_email(_config=KnotConfig(id="batch"))
            NullRateGate(
                batch=batch,
                thresholds={"email": 0.0},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is False

    async def test_empty_batch_yields_zero_rate(self) -> None:
        # 0 / 0 should not raise; we treat as 0.0 → always passes ≤ threshold
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="batch"))
            NullRateGate(
                batch=batch,
                thresholds={"email": 0.0},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is True

    async def test_multiple_columns_each_assessed(self) -> None:
        @knot
        async def two_columns() -> DataBatch:
            rows = (
                {"a": 1, "b": None},
                {"a": None, "b": 2},
                {"a": 3, "b": 4},
            )
            return DataBatch(rows=rows)

        with Tapestry() as t:
            batch = two_columns(_config=KnotConfig(id="batch"))
            NullRateGate(
                batch=batch,
                thresholds={"a": 0.5, "b": 0.0},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        # a: 1/3 = 0.333 ≤ 0.5 → pass
        # b: 1/3 = 0.333 > 0.0 → fail
        assert report.passed is False
        failed = report.failed_checks
        assert len(failed) == 1
        assert failed[0].column == "b"


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_thresholds(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "non-empty"):
                NullRateGate(batch=batch, thresholds={}, _config=KnotConfig(id="nr"))

    def test_rejects_threshold_above_one(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, r"\[0\.0, 1\.0\]"):
                NullRateGate(
                    batch=batch, thresholds={"a": 1.5},
                    _config=KnotConfig(id="nr"),
                )

    def test_rejects_non_numeric_threshold(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "must be a number"):
                NullRateGate(
                    batch=batch, thresholds={"a": "0.5"},  # type: ignore[dict-item]
                    _config=KnotConfig(id="nr"),
                )
