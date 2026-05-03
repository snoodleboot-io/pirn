"""Tests for :class:`DeleteSafeSync`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.delete_safe_sync import (
    DeleteSafeSync,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    await pool.execute_many(
        "INSERT INTO accounts (id, name) VALUES (?, ?)",
        [(1, "Alice"), (2, "Bob")],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE accounts ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  is_deleted INTEGER NOT NULL DEFAULT 0,"
        "  deleted_at TEXT"
        ")"
    )
    yield pool
    await pool.close()


def make_knot(
    source_pool: SqlitePool, target_pool: SqlitePool
) -> DeleteSafeSync:
    return DeleteSafeSync(
        source_pool=source_pool,
        source_query="SELECT id, name FROM accounts ORDER BY id",
        target_pool=target_pool,
        target_table="accounts",
        key_columns=("id",),
        non_key_columns=("name",),
        _config=KnotConfig(id="sync"),
    )


class TestConstruction:
    def test_rejects_non_pool_source(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            DeleteSafeSync(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="accounts",
                key_columns=("id",),
                non_key_columns=("name",),
                _config=KnotConfig(id="sync"),
            )

    def test_rejects_overlapping_columns(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="overlap"):
            DeleteSafeSync(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="accounts",
                key_columns=("id", "name"),
                non_key_columns=("name",),
                _config=KnotConfig(id="sync"),
            )


@pytest.mark.asyncio
class TestDeleteSafeSyncBehaviour:
    async def test_inserts_new_rows(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name FROM accounts ORDER BY id"
        )
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_soft_deletes_removed_rows(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            make_knot(source_pool, target_pool)
        result = await t2.run(RunRequest())
        assert result.succeeded
        deleted = await target_pool.fetch_all(
            "SELECT is_deleted, deleted_at FROM accounts WHERE id = 2"
        )
        assert deleted[0][0] == 1
        assert deleted[0][1] is not None

    async def test_does_not_hard_delete_rows(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            make_knot(source_pool, target_pool)
        await t2.run(RunRequest())
        total = await target_pool.fetch_all(
            "SELECT COUNT(*) FROM accounts"
        )
        assert total[0][0] == 2

    async def test_result_tracks_soft_deleted(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            make_knot(source_pool, target_pool)
        await t.run(RunRequest())
        await source_pool.execute("DELETE FROM accounts WHERE id = 2")
        with Tapestry() as t2:
            knot = make_knot(source_pool, target_pool)
        run_result = await t2.run(RunRequest())
        assert run_result.succeeded
        out = run_result.outputs[knot.config.id]
        assert out["rows_soft_deleted"] == 1
