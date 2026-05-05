"""Tests for :class:`DateDimGenerator`."""

from __future__ import annotations

import datetime
import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
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

_START = datetime.date(2026, 1, 1)
_END = datetime.date(2026, 1, 31)


async def _make_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(_CREATE_DATE_DIM)
    return pool


def _make_knot(pool: SqlitePool, **overrides: Any) -> DateDimGenerator:
    defaults: dict[str, Any] = {
        "target_pool": pool,
        "target_table": "date_dim",
        "start_date": _START,
        "end_date": _END,
        "fiscal_year_start_month": 1,
    }
    defaults.update(overrides)
    return DateDimGenerator(**defaults, _config=KnotConfig(id="ddg"))


class TestDateDimGenerator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_generates_correct_row_count(self) -> None:
        with Tapestry() as t:
            _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.pool.fetch_all("SELECT COUNT(*) FROM date_dim")
        assert rows[0][0] == 31

    async def test_date_key_format(self) -> None:
        with Tapestry() as t:
            _make_knot(
                self.pool,
                start_date=datetime.date(2026, 3, 15),
                end_date=datetime.date(2026, 3, 15),
            )
        await t.run(RunRequest())
        rows = await self.pool.fetch_all(
            "SELECT date_key, full_date, year, quarter, month, day_of_month FROM date_dim"
        )
        assert len(rows) == 1
        row = rows[0]
        assert row[0] == 20260315
        assert row[1] == "2026-03-15"
        assert row[2] == 2026
        assert row[3] == 1
        assert row[4] == 3
        assert row[5] == 15

    async def test_weekend_flag(self) -> None:
        with Tapestry() as t:
            _make_knot(
                self.pool,
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 1, 7),
            )
        await t.run(RunRequest())
        rows = await self.pool.fetch_all(
            "SELECT full_date, is_weekend FROM date_dim ORDER BY date_key"
        )
        weekends = {r[0] for r in rows if r[1] == 1}
        assert "2026-01-03" in weekends
        assert "2026-01-04" in weekends
        assert "2026-01-01" not in weekends

    async def test_fiscal_year_offset(self) -> None:
        with Tapestry() as t:
            _make_knot(
                self.pool,
                start_date=datetime.date(2026, 6, 1),
                end_date=datetime.date(2026, 6, 1),
                fiscal_year_start_month=7,
            )
        await t.run(RunRequest())
        rows = await self.pool.fetch_all("SELECT fiscal_year FROM date_dim")
        assert rows[0][0] == 2026

    async def test_fiscal_year_in_new_year(self) -> None:
        with Tapestry() as t:
            _make_knot(
                self.pool,
                start_date=datetime.date(2026, 9, 1),
                end_date=datetime.date(2026, 9, 1),
                fiscal_year_start_month=7,
            )
        await t.run(RunRequest())
        rows = await self.pool.fetch_all("SELECT fiscal_year FROM date_dim")
        assert rows[0][0] == 2027

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 31


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_target_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_table() -> str:
            return "date_dim"

        with Tapestry() as t:
            tbl_knot = emit_table(_config=KnotConfig(id="tbl"))
            DateDimGenerator(
                target_pool=self.pool,
                target_table=tbl_knot,
                start_date=datetime.date(2026, 5, 1),
                end_date=datetime.date(2026, 5, 1),
                fiscal_year_start_month=1,
                _config=KnotConfig(id="ddg"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ddg"]["rows_inserted"] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> DateDimGenerator:
        defaults: dict[str, Any] = {
            "target_pool": self.pool,
            "target_table": "date_dim",
            "start_date": _START,
            "end_date": _END,
            "fiscal_year_start_month": 1,
        }
        defaults.update(kwargs)
        with Tapestry():
            return DateDimGenerator(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DateDimGenerator, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "target_pool": self.pool,
            "target_table": "date_dim",
            "start_date": _START,
            "end_date": _END,
            "fiscal_year_start_month": 1,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_end_before_start(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "end_date"):
            await self._call(
                k,
                start_date=datetime.date(2026, 2, 1),
                end_date=datetime.date(2026, 1, 1),
            )

    async def test_rejects_invalid_fiscal_month(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "fiscal_year_start_month"):
            await self._call(k, fiscal_year_start_month=13)

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="bad table")
