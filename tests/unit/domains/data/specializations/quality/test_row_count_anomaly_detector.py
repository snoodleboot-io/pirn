"""Tests for :class:`RowCountAnomalyDetector`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.quality.row_count_anomaly_detector import (
    RowCountAnomalyDetector,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE events (id INTEGER PRIMARY KEY)")
    await p.execute_many(
        "INSERT INTO events (id) VALUES (?)", [(i,) for i in range(10)]
    )
    await p.execute(
        "CREATE TABLE row_count_audit ("
        "  table_name TEXT NOT NULL,"
        "  row_count INTEGER NOT NULL,"
        "  recorded_at TEXT NOT NULL"
        ")"
    )
    yield p
    await p.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            RowCountAnomalyDetector(
                pool="bad",  # type: ignore[arg-type]
                monitored_table="events",
                audit_table="row_count_audit",
                _config=KnotConfig(id="rca"),
            )

    def test_rejects_invalid_window(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="window"):
            RowCountAnomalyDetector(
                pool=pool,
                monitored_table="events",
                audit_table="row_count_audit",
                window=0,
                _config=KnotConfig(id="rca"),
            )

    def test_rejects_invalid_threshold(self, pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="threshold"):
            RowCountAnomalyDetector(
                pool=pool,
                monitored_table="events",
                audit_table="row_count_audit",
                threshold=-0.1,
                _config=KnotConfig(id="rca"),
            )


@pytest.mark.asyncio
class TestRowCountAnomalyDetectorBehaviour:
    async def test_first_run_returns_no_anomaly(self, pool: SqlitePool) -> None:
        with Tapestry() as t:
            RowCountAnomalyDetector(
                pool=pool,
                monitored_table="events",
                audit_table="row_count_audit",
                _config=KnotConfig(id="rca"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded

    async def test_detects_anomaly_when_count_drops_sharply(
        self, pool: SqlitePool
    ) -> None:
        for _ in range(3):
            with Tapestry() as t:
                RowCountAnomalyDetector(
                    pool=pool,
                    monitored_table="events",
                    audit_table="row_count_audit",
                    threshold=0.30,
                    _config=KnotConfig(id="rca"),
                )
            await t.run(RunRequest())
        await pool.execute("DELETE FROM events WHERE id > 0")
        with Tapestry() as t2:
            knot = RowCountAnomalyDetector(
                pool=pool,
                monitored_table="events",
                audit_table="row_count_audit",
                threshold=0.30,
                _config=KnotConfig(id="rca"),
            )
        run_result = await t2.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["anomaly_detected"] is True

    async def test_no_anomaly_within_threshold(self, pool: SqlitePool) -> None:
        for _ in range(3):
            with Tapestry() as t:
                RowCountAnomalyDetector(
                    pool=pool,
                    monitored_table="events",
                    audit_table="row_count_audit",
                    threshold=0.30,
                    _config=KnotConfig(id="rca"),
                )
            await t.run(RunRequest())
        with Tapestry() as t2:
            knot = RowCountAnomalyDetector(
                pool=pool,
                monitored_table="events",
                audit_table="row_count_audit",
                threshold=0.30,
                _config=KnotConfig(id="rca"),
            )
        run_result = await t2.run(RunRequest())
        out = run_result.outputs[knot.config.id]
        assert out["anomaly_detected"] is False
