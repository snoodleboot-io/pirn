"""Tests for :class:`MergeUpsert`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.merge_upsert import MergeUpsert
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, name, dept FROM employees ORDER BY id"
_TARGET_TABLE = "employees"
_KEY_COLS = ("id",)
_NON_KEY_COLS = ("name", "dept")


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
    )
    await src.execute_many(
        "INSERT INTO employees (id, name, dept) VALUES (?, ?, ?)",
        [(1, "Alice", "Eng"), (2, "Bob", "Sales")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, dept TEXT)"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> MergeUpsert:
    return MergeUpsert(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        key_columns=_KEY_COLS,
        non_key_columns=_NON_KEY_COLS,
        _config=KnotConfig(id="upsert"),
    )


class TestMergeUpsert(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    async def test_inserts_new_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await self.tgt.fetch_all(
            "SELECT id, name, dept FROM employees ORDER BY id"
        )
        assert rows == [(1, "Alice", "Eng"), (2, "Bob", "Sales")]

    async def test_updates_changed_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("UPDATE employees SET dept = ? WHERE id = ?", ("Finance", 1))
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        rows = await self.tgt.fetch_all("SELECT id, dept FROM employees ORDER BY id")
        assert rows == [(1, "Finance"), (2, "Sales")]

    async def test_does_not_delete_removed_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("DELETE FROM employees WHERE id = 2")
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        count = await self.tgt.fetch_all("SELECT COUNT(*) FROM employees")
        assert count[0][0] == 2

    async def test_result_tracks_inserted_and_updated(self) -> None:
        with Tapestry() as t:
            k = _make_knot(self.src, self.tgt)
        result = await t.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_inserted"] == 2
        assert out["rows_updated"] == 0


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
            MergeUpsert(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                key_columns=_KEY_COLS,
                non_key_columns=_NON_KEY_COLS,
                _config=KnotConfig(id="upsert"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["upsert"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> MergeUpsert:
        defaults: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "non_key_columns": _NON_KEY_COLS,
        }
        defaults.update(kwargs)
        with Tapestry():
            return MergeUpsert(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: MergeUpsert, **overrides: Any) -> None:
        args: dict[str, Any] = {
            "source_pool": self.src,
            "source_query": _SOURCE_QUERY,
            "target_pool": self.tgt,
            "target_table": _TARGET_TABLE,
            "key_columns": _KEY_COLS,
            "non_key_columns": _NON_KEY_COLS,
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

    async def test_rejects_overlapping_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id", "name"), non_key_columns=("name", "dept"))
