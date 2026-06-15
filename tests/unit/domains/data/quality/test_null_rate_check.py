"""Tests for :class:`pirn_data.quality.null_rate_check.NullRateCheck`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.quality.null_rate_check import NullRateCheck
from pirn_data.quality_report import QualityReport


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


class TestNullRateCheck(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_under_threshold(self) -> None:
        with Tapestry() as t:
            batch = emit_mostly_filled(_config=KnotConfig(id="batch"))
            NullRateCheck(
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
        with Tapestry() as t:
            batch = emit_mostly_filled(_config=KnotConfig(id="batch"))
            NullRateCheck(
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
            NullRateCheck(
                batch=batch,
                thresholds={"email": 0.0},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is False

    async def test_empty_batch_yields_zero_rate(self) -> None:
        with Tapestry() as t:
            batch = emit_empty(_config=KnotConfig(id="batch"))
            NullRateCheck(
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
            NullRateCheck(
                batch=batch,
                thresholds={"a": 0.5, "b": 0.0},
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is False
        failed = report.failed_checks
        assert len(failed) == 1
        assert failed[0].column == "b"


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_thresholds_from_upstream_knot(self) -> None:
        @knot
        async def emit_thresholds() -> dict:
            return {"email": 0.3}

        with Tapestry() as t:
            batch = emit_mostly_filled(_config=KnotConfig(id="batch"))
            thr_knot = emit_thresholds(_config=KnotConfig(id="thr"))
            NullRateCheck(
                batch=batch,
                thresholds=thr_knot,
                _config=KnotConfig(id="nullrate"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["nullrate"]
        assert report.passed is True


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> NullRateCheck:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        kwargs.setdefault("thresholds", {"a": 0.5})
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return NullRateCheck(batch=batch, _config=KnotConfig(id="nr"), **kwargs)

    async def test_rejects_empty_thresholds(self) -> None:
        k = self._make_knot(thresholds={})
        with self.assertRaisesRegex(TypeError, "non-empty"):
            await k.process(batch=DataBatch(), thresholds={})

    async def test_rejects_threshold_above_one(self) -> None:
        k = self._make_knot(thresholds={"a": 1.5})
        with self.assertRaisesRegex(ValueError, r"\[0\.0, 1\.0\]"):
            await k.process(batch=DataBatch(), thresholds={"a": 1.5})

    async def test_rejects_non_numeric_threshold(self) -> None:
        k = self._make_knot(thresholds={"a": "0.5"})  # type: ignore[dict-item]
        with self.assertRaisesRegex(TypeError, "must be a number"):
            await k.process(batch=DataBatch(), thresholds={"a": "0.5"})
