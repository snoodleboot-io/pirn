"""Tests for :class:`BackfillRunner`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.schema_migration.backfill_runner import (
    BackfillRunner,
)
from pirn.tapestry import Tapestry

_BATCH_QUERY = "SELECT * FROM events WHERE id > ? ORDER BY id LIMIT ?"
_SOURCE_TABLE = "events"
_KEY_COLUMN = "id"


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, val TEXT)")
    await src.execute_many(
        "INSERT INTO events VALUES (?, ?)",
        [(i, f"v{i}") for i in range(1, 6)],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, val TEXT)")
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool, **overrides: Any) -> BackfillRunner:
    defaults: dict[str, Any] = {
        "source_pool": src,
        "target_pool": tgt,
        "source_table": _SOURCE_TABLE,
        "key_column": _KEY_COLUMN,
        "batch_query_template": _BATCH_QUERY,
        "batch_size": 2,
        "resume_from_key": 0,
        "_config": KnotConfig(id="bf"),
    }
    defaults.update(overrides)
    return BackfillRunner(**defaults)


class TestBackfillRunner(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_processes_all_rows_in_batches(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        output = result.outputs["bf"]
        assert output["rows_processed"] == 5
        assert output["batches_processed"] == 3
        assert output["last_processed_key"] == 5

    async def test_resume_from_key_skips_processed(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt, resume_from_key=3, batch_size=1000,
                       _config=KnotConfig(id="bf-resume"))
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["bf-resume"]["rows_processed"] == 2

    async def test_empty_source_returns_zero(self) -> None:
        src = SqlitePool(SqliteConfig(database=":memory:"))
        await src.execute("CREATE TABLE events (id INTEGER PRIMARY KEY, val TEXT)")
        with Tapestry() as t:
            _make_knot(src, self.tgt, _config=KnotConfig(id="bf-empty"))
        result = await t.run(RunRequest())
        assert result.outputs["bf-empty"]["rows_processed"] == 0
        await src.close()


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_batch_query_from_upstream_knot(self) -> None:
        @knot
        async def emit_query() -> str:
            return _BATCH_QUERY

        with Tapestry() as t:
            q_knot = emit_query(_config=KnotConfig(id="q"))
            BackfillRunner(
                source_pool=self.src,
                target_pool=self.tgt,
                source_table=_SOURCE_TABLE,
                key_column=_KEY_COLUMN,
                batch_query_template=q_knot,
                batch_size=10,
                resume_from_key=0,
                _config=KnotConfig(id="bf-wire"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["bf-wire"]["rows_processed"] == 5


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> BackfillRunner:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "target_pool": self.tgt,
            "source_table": _SOURCE_TABLE,
            "key_column": _KEY_COLUMN,
            "batch_query_template": _BATCH_QUERY,
            "batch_size": 2,
            "resume_from_key": 0,
        }
        defaults.update(kwargs)
        with Tapestry():
            return BackfillRunner(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: BackfillRunner, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "target_pool": self.tgt,
            "source_table": _SOURCE_TABLE,
            "key_column": _KEY_COLUMN,
            "batch_query_template": _BATCH_QUERY,
            "batch_size": 2,
            "resume_from_key": 0,
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

    async def test_rejects_non_positive_batch_size(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "batch_size"):
            await self._call(k, batch_size=0)

    async def test_rejects_invalid_table_identifier(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, source_table="my events")
