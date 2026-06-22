"""Tests for :class:`WatermarkIncrementalExtract`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.ingestion.watermark_incremental_extract import (
    WatermarkIncrementalExtract,
)

_COLUMNS = ["id", "loaded_at"]
_SOURCE_TABLE = "events"
_TARGET_TABLE = "events_copy"
_WATERMARK_COLUMN = "loaded_at"


async def _make_pools(with_target_rows: bool = False) -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE events (id INTEGER PRIMARY KEY, loaded_at TEXT)"
    )
    await src.execute_many(
        "INSERT INTO events (id, loaded_at) VALUES (?, ?)",
        [(1, "2024-01-01"), (2, "2024-06-01")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE events_copy (id INTEGER PRIMARY KEY, loaded_at TEXT)"
    )
    if with_target_rows:
        await tgt.execute_many(
            "INSERT INTO events_copy (id, loaded_at) VALUES (?, ?)",
            [(1, "2024-01-01")],
        )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> WatermarkIncrementalExtract:
    return WatermarkIncrementalExtract(
        source_pool=src,
        source_table=_SOURCE_TABLE,
        columns=_COLUMNS,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        watermark_column=_WATERMARK_COLUMN,
        _config=KnotConfig(id="wie"),
    )


class TestWatermarkIncrementalExtract(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_initial_load_copies_all_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT id, loaded_at FROM events_copy ORDER BY id"
        )
        assert rows == [(1, "2024-01-01"), (2, "2024-06-01")]

    async def test_incremental_run_only_copies_new_rows(self) -> None:
        src, tgt = await _make_pools(with_target_rows=True)
        with Tapestry() as t:
            WatermarkIncrementalExtract(
                source_pool=src,
                source_table=_SOURCE_TABLE,
                columns=_COLUMNS,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                watermark_column=_WATERMARK_COLUMN,
                _config=KnotConfig(id="wie"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await tgt.fetch_all(
            "SELECT id FROM events_copy ORDER BY id"
        )
        assert rows == [(1,), (2,)]
        await src.close()
        await tgt.close()

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

    async def test_source_pool_from_upstream_knot(self) -> None:
        src = self.src
        tgt = self.tgt

        @knot
        async def emit_pool() -> SqlitePool:
            return src

        with Tapestry() as t:
            p_knot = emit_pool(_config=KnotConfig(id="pool"))
            WatermarkIncrementalExtract(
                source_pool=p_knot,
                source_table=_SOURCE_TABLE,
                columns=_COLUMNS,
                target_pool=tgt,
                target_table=_TARGET_TABLE,
                watermark_column=_WATERMARK_COLUMN,
                _config=KnotConfig(id="wie"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["wie"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> WatermarkIncrementalExtract:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_table": _SOURCE_TABLE,
            "columns": _COLUMNS,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "watermark_column": _WATERMARK_COLUMN,
        }
        defaults.update(kwargs)
        with Tapestry():
            return WatermarkIncrementalExtract(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: WatermarkIncrementalExtract, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_table": _SOURCE_TABLE,
            "columns": _COLUMNS,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "watermark_column": _WATERMARK_COLUMN,
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

    async def test_rejects_empty_source_table(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_table"):
            await self._call(k, source_table="")

    async def test_rejects_empty_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "columns"):
            await self._call(k, columns=[])
