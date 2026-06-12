"""Tests for :class:`FullRefreshExtract`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.ingestion.full_refresh_extract import (
    FullRefreshExtract,
)
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, sku FROM products ORDER BY id"
_INSERT_QUERY = "INSERT INTO products (id, sku) VALUES (?, ?)"
_TARGET_TABLE = "products"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL)"
    )
    await src.execute_many(
        "INSERT INTO products (id, sku) VALUES (?, ?)",
        [(1, "A1"), (2, "A2"), (3, "A3")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT NOT NULL)"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> FullRefreshExtract:
    return FullRefreshExtract(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        insert_query=_INSERT_QUERY,
        _config=KnotConfig(id="refresh"),
    )


class TestFullRefreshExtract(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_loads_into_empty_target(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT id, sku FROM products ORDER BY id")
        assert rows == [(1, "A1"), (2, "A2"), (3, "A3")]

    async def test_subsequent_run_drops_and_reloads(self) -> None:
        await self.tgt.execute_many(
            "INSERT INTO products (id, sku) VALUES (?, ?)",
            [(99, "STALE")],
        )
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT id FROM products ORDER BY id")
        assert rows == [(1,), (2,), (3,)]

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 3
        assert out["succeeded"] is True


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_source_query_from_upstream_knot(self) -> None:
        src, tgt = self.src, self.tgt

        @knot
        async def emit_query() -> str:
            return _SOURCE_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            FullRefreshExtract(
                source_pool=src,
                source_query=q_knot,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                insert_query=_INSERT_QUERY,
                _config=KnotConfig(id="refresh"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["refresh"]["rows_inserted"] == 3


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> FullRefreshExtract:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "insert_query": _INSERT_QUERY,
        }
        defaults.update(kwargs)
        with Tapestry():
            return FullRefreshExtract(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: FullRefreshExtract, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "insert_query": _INSERT_QUERY,
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

    async def test_rejects_empty_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "target_table"):
            await self._call(k, target_table="")

    async def test_rejects_non_alphanumeric_target_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "alphanumeric"):
            await self._call(k, target_table="products; DROP TABLE--")
