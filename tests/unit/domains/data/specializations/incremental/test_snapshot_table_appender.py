"""Tests for :class:`SnapshotTableAppender`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.incremental.snapshot_table_appender import (
    SnapshotTableAppender,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
    )
    await pool.execute_many(
        "INSERT INTO products (id, name) VALUES (?, ?)",
        [(1, "Alpha"), (2, "Beta")],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE products_snapshot ("
        "  id INTEGER,"
        "  name TEXT,"
        "  _snapshot_date TEXT NOT NULL"
        ")"
    )
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool_source(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            SnapshotTableAppender(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="products_snapshot",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )

    def test_rejects_non_pool_target(self, source_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            SnapshotTableAppender(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool="bad",  # type: ignore[arg-type]
                target_table="products_snapshot",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )

    def test_rejects_empty_source_query(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="source_query"):
            SnapshotTableAppender(
                source_pool=source_pool,
                source_query="",
                target_pool=target_pool,
                target_table="products_snapshot",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )

    def test_rejects_invalid_table_identifier(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            SnapshotTableAppender(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="bad table name",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )


@pytest.mark.asyncio
class TestSnapshotTableAppenderBehaviour:
    async def test_appends_all_source_rows_with_snapshot_date(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            SnapshotTableAppender(
                source_pool=source_pool,
                source_query="SELECT id, name FROM products ORDER BY id",
                target_pool=target_pool,
                target_table="products_snapshot",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name FROM products_snapshot ORDER BY id"
        )
        assert rows == [(1, "Alpha"), (2, "Beta")]
        date_rows = await target_pool.fetch_all(
            "SELECT DISTINCT _snapshot_date FROM products_snapshot"
        )
        assert len(date_rows) == 1
        assert date_rows[0][0] is not None

    async def test_second_run_appends_another_snapshot(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        for _ in range(2):
            with Tapestry() as t:
                SnapshotTableAppender(
                    source_pool=source_pool,
                    source_query="SELECT id, name FROM products ORDER BY id",
                    target_pool=target_pool,
                    target_table="products_snapshot",
                    source_columns=("id", "name"),
                    _config=KnotConfig(id="snap"),
                )
            assert (await t.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id FROM products_snapshot ORDER BY id"
        )
        assert len(rows) == 4

    async def test_result_contains_rows_appended(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            knot = SnapshotTableAppender(
                source_pool=source_pool,
                source_query="SELECT id, name FROM products",
                target_pool=target_pool,
                target_table="products_snapshot",
                source_columns=("id", "name"),
                _config=KnotConfig(id="snap"),
            )
        run_result = await t.run(RunRequest())
        assert run_result.succeeded
        knot_result = run_result.outputs[knot.config.id]
        assert knot_result["rows_appended"] == 2
