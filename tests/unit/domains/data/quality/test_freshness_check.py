"""Tests for :class:`pirn_data.quality.freshness_check.FreshnessCheck`."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.data_batch import DataBatch
from pirn_data.quality.freshness_check import FreshnessCheck
from pirn_data.quality_report import QualityReport


def _batch_with_newest(age: timedelta):
    """Factory: a one-row batch whose ``updated_at`` is ``age`` ago."""
    @knot
    async def emit() -> DataBatch:
        when = datetime.now(UTC) - age
        return DataBatch(rows=({"id": 1, "updated_at": when},))
    return emit


class TestFreshnessCheck(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_newest_is_recent(self) -> None:
        with Tapestry() as t:
            batch = _batch_with_newest(timedelta(minutes=30))(_config=KnotConfig(id="batch"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=timedelta(hours=1),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True

    async def test_fails_when_newest_is_too_old(self) -> None:
        with Tapestry() as t:
            batch = _batch_with_newest(timedelta(hours=25))(_config=KnotConfig(id="batch"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=timedelta(hours=24),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is False

    async def test_empty_batch_fails(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        with Tapestry() as t:
            batch = empty(_config=KnotConfig(id="batch"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=timedelta(hours=1),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is False
        assert any(c.name == "freshness_no_timestamp" for c in report.failed_checks)

    async def test_naive_datetime_treated_as_utc(self) -> None:
        @knot
        async def naive() -> DataBatch:
            now_naive = datetime.utcnow()
            return DataBatch(rows=({"updated_at": now_naive},))

        with Tapestry() as t:
            batch = naive(_config=KnotConfig(id="batch"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=timedelta(minutes=5),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True

    async def test_picks_newest_across_rows(self) -> None:
        @knot
        async def mixed() -> DataBatch:
            now = datetime.now(UTC)
            rows = (
                {"updated_at": now - timedelta(days=10)},
                {"updated_at": now - timedelta(minutes=5)},
                {"updated_at": now - timedelta(hours=2)},
            )
            return DataBatch(rows=rows)

        with Tapestry() as t:
            batch = mixed(_config=KnotConfig(id="batch"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=timedelta(minutes=10),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_column_from_upstream_knot(self) -> None:
        @knot
        async def emit_column() -> str:
            return "updated_at"

        with Tapestry() as t:
            batch = _batch_with_newest(timedelta(minutes=30))(_config=KnotConfig(id="batch"))
            col_knot = emit_column(_config=KnotConfig(id="col"))
            FreshnessCheck(
                batch=batch,
                column=col_knot,
                max_age=timedelta(hours=1),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True

    async def test_max_age_from_upstream_knot(self) -> None:
        @knot
        async def emit_max_age() -> timedelta:
            return timedelta(hours=1)

        with Tapestry() as t:
            batch = _batch_with_newest(timedelta(minutes=30))(_config=KnotConfig(id="batch"))
            age_knot = emit_max_age(_config=KnotConfig(id="age"))
            FreshnessCheck(
                batch=batch,
                column="updated_at",
                max_age=age_knot,
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: object) -> FreshnessCheck:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()

        kwargs.setdefault("column", "t")
        kwargs.setdefault("max_age", timedelta(hours=1))
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            return FreshnessCheck(batch=batch, _config=KnotConfig(id="f"), **kwargs)

    async def test_rejects_empty_column(self) -> None:
        k = self._make_knot(column="")
        with self.assertRaisesRegex(ValueError, "non-empty"):
            await k.process(
                batch=DataBatch(),
                column="",
                max_age=timedelta(hours=1),
            )

    async def test_rejects_non_timedelta_max_age(self) -> None:
        k = self._make_knot(max_age=3600)  # type: ignore[arg-type]
        with self.assertRaisesRegex(TypeError, "timedelta"):
            await k.process(
                batch=DataBatch(),
                column="t",
                max_age=3600,  # type: ignore[arg-type]
            )

    async def test_rejects_zero_or_negative_max_age(self) -> None:
        k = self._make_knot(max_age=timedelta(0))
        with self.assertRaisesRegex(ValueError, "positive"):
            await k.process(
                batch=DataBatch(),
                column="t",
                max_age=timedelta(0),
            )
