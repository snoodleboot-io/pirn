"""Tests for :class:`ReferentialIntegrityCheck`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.quality.referential_integrity_check import (
    ReferentialIntegrityCheck,
)

_FACT_TABLE = "orders"
_FACT_COL = "customer_id"
_DIM_TABLE = "customers"
_DIM_COL = "id"


async def _make_pool() -> SqlitePool:
    p = SqlitePool(SqliteConfig(database=":memory:"))
    await p.execute("CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)")
    await p.execute_many(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    await p.execute(
        "CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER)"
    )
    await p.execute_many(
        "INSERT INTO orders (id, customer_id) VALUES (?, ?)",
        [(1, 1), (2, 2), (3, 99)],
    )
    return p


def _make_knot(pool: SqlitePool) -> ReferentialIntegrityCheck:
    return ReferentialIntegrityCheck(
        pool=pool,
        fact_table=_FACT_TABLE,
        fact_column=_FACT_COL,
        dimension_table=_DIM_TABLE,
        dimension_column=_DIM_COL,
        _config=KnotConfig(id="ri"),
    )


class TestReferentialIntegrityCheck(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_detects_orphaned_rows(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        out = result.outputs[k.config.id]
        assert out["orphaned_rows"] == 1
        assert out["has_orphans"] is True
        assert abs(out["orphaned_pct"] - 100 / 3) < 0.01

    async def test_clean_table_has_no_orphans(self) -> None:
        await self.pool.execute("DELETE FROM orders WHERE id = 3")
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["orphaned_rows"] == 0
        assert out["has_orphans"] is False

    async def test_result_contains_expected_keys(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.pool)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["fact_table"] == _FACT_TABLE
        assert out["fact_column"] == _FACT_COL
        assert out["dimension_table"] == _DIM_TABLE
        assert out["dimension_column"] == _DIM_COL


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    async def test_fact_table_from_upstream_knot(self) -> None:
        @knot
        async def emit_table() -> str:
            return _FACT_TABLE

        with Tapestry() as t:
            tbl_knot = emit_table(_config=KnotConfig(id="tbl"))
            ReferentialIntegrityCheck(
                pool=self.pool,
                fact_table=tbl_knot,
                fact_column=_FACT_COL,
                dimension_table=_DIM_TABLE,
                dimension_column=_DIM_COL,
                _config=KnotConfig(id="ri"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["ri"]["orphaned_rows"] == 1


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.pool = await _make_pool()

    async def asyncTearDown(self) -> None:
        await self.pool.close()

    def _make_knot(self, **kwargs: Any) -> ReferentialIntegrityCheck:
        defaults: dict[str, Any] = {
            "pool": self.pool,
            "fact_table": _FACT_TABLE,
            "fact_column": _FACT_COL,
            "dimension_table": _DIM_TABLE,
            "dimension_column": _DIM_COL,
        }
        defaults.update(kwargs)
        with Tapestry():
            return ReferentialIntegrityCheck(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: ReferentialIntegrityCheck, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "pool": self.pool,
            "fact_table": _FACT_TABLE,
            "fact_column": _FACT_COL,
            "dimension_table": _DIM_TABLE,
            "dimension_column": _DIM_COL,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, pool="bad")

    async def test_rejects_invalid_fact_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, fact_table="bad table")

    async def test_rejects_invalid_dimension_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, dimension_table="bad-dim")
