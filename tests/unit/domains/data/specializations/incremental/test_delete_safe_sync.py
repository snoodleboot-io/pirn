"""Tests for :class:`DeleteSafeSync`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.delete_safe_sync import DeleteSafeSync
from pirn.tapestry import Tapestry

_SOURCE_QUERY = "SELECT id, name FROM accounts ORDER BY id"
_TARGET_TABLE = "accounts"
_KEY_COLS = ("id",)
_NON_KEY_COLS = ("name",)


async def _make_pools() -> tuple[SqlitePool, SqlitePool]:
    src = SqlitePool(SqliteConfig(database=":memory:"))
    await src.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    await src.execute_many(
        "INSERT INTO accounts (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    tgt = SqlitePool(SqliteConfig(database=":memory:"))
    await tgt.execute(
        "CREATE TABLE accounts ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  is_deleted INTEGER NOT NULL DEFAULT 0,"
        "  deleted_at TEXT"
        ")"
    )
    return src, tgt


def _make_knot(src: SqlitePool, tgt: SqlitePool) -> DeleteSafeSync:
    return DeleteSafeSync(
        source_pool=src,
        source_query=_SOURCE_QUERY,
        target_pool=tgt,
        target_table=_TARGET_TABLE,
        key_columns=_KEY_COLS,
        non_key_columns=_NON_KEY_COLS,
        _config=KnotConfig(id="sync"),
    )


class TestDeleteSafeSync(unittest.IsolatedAsyncioTestCase):
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
        rows = await self.tgt.fetch_all("SELECT id, name FROM accounts ORDER BY id")
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_soft_deletes_removed_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        result = await t2.run(RunRequest())
        assert result.succeeded
        deleted = await self.tgt.fetch_all(
            "SELECT is_deleted, deleted_at FROM accounts WHERE id = 2"
        )
        assert deleted[0][0] == 1
        assert deleted[0][1] is not None

    async def test_does_not_hard_delete_rows(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            _make_knot(self.src, self.tgt)
        await t2.run(RunRequest())
        total = await self.tgt.fetch_all("SELECT COUNT(*) FROM accounts")
        assert total[0][0] == 2

    async def test_result_tracks_soft_deleted(self) -> None:
        with Tapestry() as t:
            _make_knot(self.src, self.tgt)
        await t.run(RunRequest())
        await self.src.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            k = _make_knot(self.src, self.tgt)
        result = await t2.run(RunRequest())
        out = result.outputs[k.config.id]
        assert out["rows_soft_deleted"] == 1


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
            DeleteSafeSync(
                source_pool=self.src,
                source_query=q_knot,
                target_pool=self.tgt,
                target_table=_TARGET_TABLE,
                key_columns=_KEY_COLS,
                non_key_columns=_NON_KEY_COLS,
                _config=KnotConfig(id="sync"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["sync"]["rows_inserted"] == 2


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.src, self.tgt = await _make_pools()

    async def asyncTearDown(self) -> None:
        await self.src.close()
        await self.tgt.close()

    def _make_knot(self, **kwargs: Any) -> DeleteSafeSync:
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
            return DeleteSafeSync(**defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: DeleteSafeSync, **overrides: Any) -> None:
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

    async def test_rejects_overlapping_columns(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "overlap"):
            await self._call(k, key_columns=("id", "name"), non_key_columns=("name",))

    async def test_rejects_empty_source_query(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "source_query"):
            await self._call(k, source_query="")
