"""Tests for :class:`SilverCleanTransform`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.medallion.silver_clean_transform import (
    SilverCleanTransform,
)

_SOURCE_QUERY = "SELECT id, name FROM bronze_t ORDER BY id"
_COLUMN_NAMES = ["id", "name"]
_TARGET_TABLE = "silver_t"
_CASTS: dict[str, type] = {"id": int}
_FILTER = lambda row: bool(row.get("id"))  # noqa: E731
_PRIMARY_KEYS = ["id"]


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute("CREATE TABLE bronze_t (id INTEGER, name TEXT)")
    await src.execute_many(
        "INSERT INTO bronze_t (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob"), (2, "BobDup")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute("CREATE TABLE silver_t (id INTEGER PRIMARY KEY, name TEXT)")
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> SilverCleanTransform:
    return SilverCleanTransform(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        column_names=_COLUMN_NAMES,
        casts=_CASTS,
        filter_predicate=_FILTER,
        primary_keys=_PRIMARY_KEYS,
        _config=KnotConfig(id="silver"),
    )


class TestSilverCleanTransform(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_deduplicates_and_writes_silver(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT id, name FROM silver_t ORDER BY id")
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_filters_rows_with_null_id(self) -> None:
        await self.src.execute("INSERT INTO bronze_t (id, name) VALUES (?, ?)", (None, "Ghost"))
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all("SELECT COUNT(*) FROM silver_t")
        assert rows[0][0] == 2

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["succeeded"] is True
        assert out["rows_inserted"] == 2


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
            q = emit_query(_config=KnotConfig(id="q"))
            SilverCleanTransform(
                source_pool=src,
                source_query=q,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                column_names=_COLUMN_NAMES,
                casts=_CASTS,
                filter_predicate=_FILTER,
                primary_keys=_PRIMARY_KEYS,
                _config=KnotConfig(id="silver"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["silver"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> SilverCleanTransform:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "column_names": _COLUMN_NAMES,
            "casts": _CASTS,
            "filter_predicate": _FILTER,
            "primary_keys": _PRIMARY_KEYS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return SilverCleanTransform(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: SilverCleanTransform, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "column_names": _COLUMN_NAMES,
            "casts": _CASTS,
            "filter_predicate": _FILTER,
            "primary_keys": _PRIMARY_KEYS,
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

    async def test_rejects_empty_column_names(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "column_names"):
            await self._call(k, column_names=[])

    async def test_rejects_empty_primary_keys(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "primary_keys"):
            await self._call(k, primary_keys=[])
