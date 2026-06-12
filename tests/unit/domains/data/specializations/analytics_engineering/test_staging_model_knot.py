"""Tests for :class:`StagingModelKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.analytics_engineering.staging_model_knot import (
    StagingModelKnot,
)
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT order_id, cust_id, amt FROM raw_orders"
_TARGET_TABLE = "stg_orders"
_COLUMN_MAP = {"order_id": "order_id", "cust_id": "customer_id", "amt": "amount"}


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE raw_orders (order_id INTEGER, cust_id INTEGER, amt REAL)"
    )
    await src.execute_many(
        "INSERT INTO raw_orders VALUES (?, ?, ?)",
        [(1, 10, 99.9), (2, 11, 49.5)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE stg_orders "
        "(order_id INTEGER, customer_id INTEGER, amount REAL, _loaded_at TEXT)"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> StagingModelKnot:
    return StagingModelKnot(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        column_map=_COLUMN_MAP,
        _config=KnotConfig(id="staging"),
    )


class TestStagingModelKnot(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_writes_rows_with_loaded_at(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT order_id, customer_id, amount FROM stg_orders ORDER BY order_id"
        )
        assert rows == [(1, 10, 99.9), (2, 11, 49.5)]
        loaded_at_rows = await self.tgt.fetch_all(
            "SELECT _loaded_at FROM stg_orders WHERE _loaded_at IS NOT NULL"
        )
        assert len(loaded_at_rows) == 2

    async def test_returns_rows_written_count(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs[k.config.id]["rows_written"] == 2

    async def test_empty_source_writes_nothing(self) -> None:
        await self.src.execute("DELETE FROM raw_orders")
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT * FROM stg_orders")
        assert rows == []


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            StagingModelKnot(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                column_map=_COLUMN_MAP,
                _config=KnotConfig(id="staging"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["staging"]["rows_written"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> StagingModelKnot:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "column_map": _COLUMN_MAP,
        }
        defaults.update(kwargs)
        with Tapestry():
            return StagingModelKnot(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: StagingModelKnot, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "column_map": _COLUMN_MAP,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_non_pool_target(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, target_pool="bad")

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")

    async def test_rejects_empty_column_map(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_map"):
            await self._call(k, column_map={})

    async def test_rejects_invalid_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, target_table="stg; DROP TABLE x")
