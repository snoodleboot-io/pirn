"""Tests for :class:`BronzeRawIngest`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.medallion.bronze_raw_ingest import (
    BronzeRawIngest,
)
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, name FROM customers ORDER BY id"
_SOURCE_COLUMNS = ["id", "name"]
_TARGET_TABLE = "bronze_customers"
_SOURCE_URI = "db://src/customers"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT)"
    )
    await src.execute_many(
        "INSERT INTO customers (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE bronze_customers "
        "(id INTEGER, name TEXT, _ingested_at TEXT, _source_uri TEXT)"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> BronzeRawIngest:
    return BronzeRawIngest(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        source_columns=_SOURCE_COLUMNS,
        source_uri=_SOURCE_URI,
        _config=KnotConfig(id="bronze"),
    )


class TestBronzeRawIngest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_inserts_rows_with_metadata(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT id, name, _source_uri FROM bronze_customers ORDER BY id"
        )
        assert rows[0] == (1, "Alice", _SOURCE_URI)
        assert rows[1] == (2, "Bob", _SOURCE_URI)

    async def test_ingested_at_is_iso_string(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        rows = await self.tgt.fetch_all(
            "SELECT _ingested_at FROM bronze_customers LIMIT 1"
        )
        assert "T" in rows[0][0]

    async def test_result_tracks_rows_inserted(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 2
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
            BronzeRawIngest(
                source_pool=src,
                source_query=q_knot,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                source_columns=_SOURCE_COLUMNS,
                source_uri=_SOURCE_URI,
                _config=KnotConfig(id="bronze"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["bronze"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> BronzeRawIngest:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SOURCE_COLUMNS,
            "source_uri": _SOURCE_URI,
        }
        defaults.update(kwargs)
        with Tapestry():
            return BronzeRawIngest(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: BronzeRawIngest, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "source_columns": _SOURCE_COLUMNS,
            "source_uri": _SOURCE_URI,
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

    async def test_rejects_empty_source_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_columns"):
            await self._call(k, source_columns=[])

    async def test_rejects_empty_source_uri(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_uri"):
            await self._call(k, source_uri="")
