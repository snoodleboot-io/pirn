"""Tests for :class:`FactTableLoad`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.dimensional.fact_table_load import FactTableLoad
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT sale_id, customer_id, amount FROM sales"
_TARGET_TABLE = "fact_sales"
_SOURCE_COLS = ("sale_id", "customer_id", "amount")
_FACT_COLS = ("sale_id", "amount")
_DIM_LOOKUPS = [
    {
        "dim_table": "customers",
        "natural_key_columns": ("customer_id",),
        "surrogate_key_column": "customer_sk",
        "fact_fk_column": "customer_sk",
        "is_current_column": "is_current",
    }
]


async def _make_source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE sales ("
        "  sale_id INTEGER PRIMARY KEY,"
        "  customer_id INTEGER NOT NULL,"
        "  amount REAL NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO sales (sale_id, customer_id, amount) VALUES (?, ?, ?)",
        [(1, 10, 99.99), (2, 20, 149.50), (3, 99, 25.00)],
    )
    return pool


async def _make_dim_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  customer_sk INTEGER PRIMARY KEY,"
        "  customer_id INTEGER NOT NULL,"
        "  is_current INTEGER NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (customer_sk, customer_id, is_current) VALUES (?, ?, ?)",
        [(1001, 10, 1), (1002, 20, 1)],
    )
    return pool


async def _make_target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE fact_sales ("
        "  sale_id INTEGER NOT NULL,"
        "  amount REAL NOT NULL,"
        "  customer_sk INTEGER NOT NULL"
        ")"
    )
    return pool


def _make_knot(
    src: SqlitePool,
    tgt: SqlitePool,
    dim: SqlitePool,
    **overrides: Any,
) -> FactTableLoad:
    lookups = [dict(spec, dim_pool=dim) for spec in _DIM_LOOKUPS]
    defaults: dict[str, Any] = {
        "source_pool": src,
        "source_query": _SOURCE_QUERY,
        "target_pool": tgt,
        "target_table": _TARGET_TABLE,
        "source_columns": _SOURCE_COLS,
        "fact_columns": _FACT_COLS,
        "dim_lookups": lookups,
        "unknown_sk": -1,
    }
    defaults.update(overrides)
    return FactTableLoad(**defaults, _config=KnotConfig(id="fact"))


class TestFactTableLoad(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.dim = await _make_dim_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.dim.close()
        await self.tgt.close()

    async def test_resolves_dimension_keys(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt, self.dim)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT sale_id, customer_sk FROM fact_sales ORDER BY sale_id"
        )
        assert len(rows) == 3
        sk_map = {r[0]: r[1] for r in rows}
        assert sk_map[1] == 1001
        assert sk_map[2] == 1002

    async def test_late_arriving_dim_uses_unknown_sk(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt, self.dim)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT sale_id, customer_sk FROM fact_sales WHERE sale_id = 3"
        )
        assert rows[0][1] == -1

    async def test_late_arriving_count_in_output(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt, self.dim)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["late_arriving_count"] == 1


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.dim = await _make_dim_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.dim.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        dim = self.dim
        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            FactTableLoad(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                source_columns=_SOURCE_COLS,
                fact_columns=_FACT_COLS,
                dim_lookups=[dict(spec, dim_pool=dim) for spec in _DIM_LOOKUPS],
                unknown_sk=-1,
                _config=KnotConfig(id="fact"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["fact"]["rows_inserted"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src = await _make_source_pool()
        self.dim = await _make_dim_pool()
        self.tgt = await _make_target_pool()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.dim.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> FactTableLoad:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SOURCE_COLS,
            "fact_columns": _FACT_COLS,
            "dim_lookups": [dict(spec, dim_pool=self.dim) for spec in _DIM_LOOKUPS],
            "unknown_sk": -1,
        }
        defaults.update(kwargs)
        with Tapestry():
            return FactTableLoad(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: FactTableLoad, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SOURCE_COLS,
            "fact_columns": _FACT_COLS,
            "dim_lookups": [dict(spec, dim_pool=self.dim) for spec in _DIM_LOOKUPS],
            "unknown_sk": -1,
        }
        args.update(overrides)
        await k.process(**args)

    async def test_rejects_non_pool_source(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(TypeError, "DatabaseConnectionPool"):
            await self._call(k, source_pool="bad")

    async def test_rejects_empty_dim_lookups(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "dim_lookups"):
            await self._call(k, dim_lookups=[])

    async def test_rejects_missing_required_lookup_key(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "missing key"):
            await self._call(k, dim_lookups=[{"dim_table": "customers"}])

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")
