"""Tests for :class:`pirn.domains.data.quality.freshness_gate.FreshnessGate`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.quality.freshness_gate import FreshnessGate
from pirn.domains.data.quality_report import QualityReport
from pirn.tapestry import Tapestry


def _batch_with_newest(age: timedelta):
    """Factory: a one-row batch whose ``updated_at`` is ``age`` ago."""
    @knot
    async def emit() -> DataBatch:
        when = datetime.now(timezone.utc) - age
        return DataBatch(rows=({"id": 1, "updated_at": when},))
    return emit


class TestFreshnessGate(unittest.IsolatedAsyncioTestCase):
    async def test_passes_when_newest_is_recent(self) -> None:
        with Tapestry() as t:
            batch = _batch_with_newest(timedelta(minutes=30))(_config=KnotConfig(id="batch"))
            FreshnessGate(
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
            FreshnessGate(
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
            FreshnessGate(
                batch=batch,
                column="updated_at",
                max_age=timedelta(hours=1),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is False
        assert any(
            c.name == "freshness_no_timestamp" for c in report.failed_checks
        )

    async def test_naive_datetime_treated_as_utc(self) -> None:
        @knot
        async def naive() -> DataBatch:
            # No tzinfo on this datetime — should be treated as UTC.
            now_naive = datetime.utcnow()
            return DataBatch(rows=({"updated_at": now_naive},))

        with Tapestry() as t:
            batch = naive(_config=KnotConfig(id="batch"))
            FreshnessGate(
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
            now = datetime.now(timezone.utc)
            rows = (
                {"updated_at": now - timedelta(days=10)},
                {"updated_at": now - timedelta(minutes=5)},  # newest
                {"updated_at": now - timedelta(hours=2)},
            )
            return DataBatch(rows=rows)

        with Tapestry() as t:
            batch = mixed(_config=KnotConfig(id="batch"))
            FreshnessGate(
                batch=batch,
                column="updated_at",
                max_age=timedelta(minutes=10),
                _config=KnotConfig(id="freshness"),
            )
        result = await t.run(RunRequest())
        report: QualityReport = result.outputs["freshness"]
        assert report.passed is True


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_column(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                FreshnessGate(
                    batch=batch, column="", max_age=timedelta(hours=1),
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_non_timedelta_max_age(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(TypeError, "timedelta"):
                FreshnessGate(
                    batch=batch, column="t", max_age=3600,  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )

    def test_rejects_zero_or_negative_max_age(self) -> None:
        @knot
        async def empty() -> DataBatch:
            return DataBatch()
        with Tapestry():
            batch = empty(_config=KnotConfig(id="empty"))
            with self.assertRaisesRegex(ValueError, "positive"):
                FreshnessGate(
                    batch=batch, column="t", max_age=timedelta(0),
                    _config=KnotConfig(id="f"),
                )
