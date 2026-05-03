"""Tests for :class:`DateDimGenerator`."""

from __future__ import annotations

import datetime

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.date_dim_generator import (
    DateDimGenerator,
)
from pirn.tapestry import Tapestry

_CREATE_DATE_DIM = (
    "CREATE TABLE date_dim ("
    "  date_key INTEGER PRIMARY KEY,"
    "  full_date TEXT NOT NULL,"
    "  year INTEGER NOT NULL,"
    "  quarter INTEGER NOT NULL,"
    "  month INTEGER NOT NULL,"
    "  week INTEGER NOT NULL,"
    "  day_of_month INTEGER NOT NULL,"
    "  day_of_week INTEGER NOT NULL,"
    "  is_weekend INTEGER NOT NULL,"
    "  fiscal_year INTEGER NOT NULL"
    ")"
)


@pytest.fixture
async def target_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "date_dim.db")))
    await pool.execute(_CREATE_DATE_DIM)
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool(self) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            DateDimGenerator(
                target_pool="bad",  # type: ignore[arg-type]
                target_table="date_dim",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 31),
                _config=KnotConfig(id="ddg"),
            )

    def test_rejects_end_before_start(self, target_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="end_date"):
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 2, 1),
                end_date=datetime.date(2026, 1, 1),
                _config=KnotConfig(id="ddg"),
            )

    def test_rejects_invalid_fiscal_month(self, target_pool: SqlitePool) -> None:
        with pytest.raises(ValueError, match="fiscal_year_start_month"):
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 31),
                fiscal_year_start_month=13,
                _config=KnotConfig(id="ddg"),
            )

    def test_rejects_invalid_table_identifier(
        self, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            DateDimGenerator(
                target_pool=target_pool,
                target_table="bad table",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 1),
                _config=KnotConfig(id="ddg"),
            )


@pytest.mark.asyncio
class TestDateDimGeneratorBehaviour:
    async def test_generates_correct_row_count(
        self, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 31),
                _config=KnotConfig(id="ddg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all("SELECT COUNT(*) FROM date_dim")
        assert rows[0][0] == 31

    async def test_date_key_format(self, target_pool: SqlitePool) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 3, 15),
                end_date=datetime.date(2026, 3, 15),
                _config=KnotConfig(id="ddg"),
            )
        await t.run(RunRequest())
        rows = await target_pool.fetch_all(
            "SELECT date_key, full_date, year, quarter, month, day_of_month "
            "FROM date_dim"
        )
        assert len(rows) == 1
        row = rows[0]
        assert row[0] == 20260315
        assert row[1] == "2026-03-15"
        assert row[2] == 2026
        assert row[3] == 1
        assert row[4] == 3
        assert row[5] == 15

    async def test_weekend_flag(self, target_pool: SqlitePool) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 7),
                _config=KnotConfig(id="ddg"),
            )
        await t.run(RunRequest())
        rows = await target_pool.fetch_all(
            "SELECT full_date, is_weekend FROM date_dim ORDER BY date_key"
        )
        weekends = {r[0] for r in rows if r[1] == 1}
        assert "2026-01-03" in weekends
        assert "2026-01-04" in weekends
        assert "2026-01-01" not in weekends

    async def test_fiscal_year_offset(self, target_pool: SqlitePool) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 6, 1),
                end_date=datetime.date(2026, 6, 1),
                fiscal_year_start_month=7,
                _config=KnotConfig(id="ddg"),
            )
        await t.run(RunRequest())
        rows = await target_pool.fetch_all("SELECT fiscal_year FROM date_dim")
        assert rows[0][0] == 2026

    async def test_fiscal_year_in_new_year(self, target_pool: SqlitePool) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 9, 1),
                end_date=datetime.date(2026, 9, 1),
                fiscal_year_start_month=7,
                _config=KnotConfig(id="ddg"),
            )
        await t.run(RunRequest())
        rows = await target_pool.fetch_all("SELECT fiscal_year FROM date_dim")
        assert rows[0][0] == 2027

    async def test_single_day_range(self, target_pool: SqlitePool) -> None:
        with Tapestry() as t:
            DateDimGenerator(
                target_pool=target_pool,
                target_table="date_dim",
                start_date=datetime.date(2026, 5, 1),
                end_date=datetime.date(2026, 5, 1),
                _config=KnotConfig(id="ddg"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all("SELECT COUNT(*) FROM date_dim")
        assert rows[0][0] == 1
