"""Tests for :class:`ScdType3PreviousValue`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig
from pirn.domains.connectors.databases.sqlite_pool import SqlitePool
from pirn.domains.data.specializations.scd.scd_type_3_previous_value import (
    ScdType3PreviousValue,
)
from pirn.tapestry import Tapestry


@pytest.fixture
async def source_pool() -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=":memory:"))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  region TEXT NOT NULL"
        ")"
    )
    await pool.execute_many(
        "INSERT INTO customers (id, name, region) VALUES (?, ?, ?)",
        [(1, "Alice", "EU"), (2, "Bob", "US")],
    )
    yield pool
    await pool.close()


@pytest.fixture
async def target_pool(tmp_path) -> SqlitePool:
    pool = SqlitePool(SqliteConfig(database=str(tmp_path / "scd3.db")))
    await pool.execute(
        "CREATE TABLE customers ("
        "  id INTEGER PRIMARY KEY,"
        "  name TEXT NOT NULL,"
        "  region TEXT NOT NULL,"
        "  name_previous TEXT,"
        "  region_previous TEXT"
        ")"
    )
    yield pool
    await pool.close()


class TestConstruction:
    def test_rejects_non_pool_source(self, target_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ScdType3PreviousValue(
                source_pool="bad",  # type: ignore[arg-type]
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )

    def test_rejects_non_pool_target(self, source_pool: SqlitePool) -> None:
        with pytest.raises(TypeError, match="DatabaseConnectionPool"):
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool="bad",  # type: ignore[arg-type]
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )

    def test_rejects_empty_source_query(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="source_query"):
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )

    def test_rejects_overlapping_key_and_tracked(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="overlap"):
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id", "name"),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )

    def test_rejects_invalid_table_identifier(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT 1",
                target_pool=target_pool,
                target_table="bad table",
                key_columns=("id",),
                tracked_columns=("name",),
                _config=KnotConfig(id="scd3"),
            )


@pytest.mark.asyncio
class TestScdType3Behaviour:
    async def test_first_run_inserts_with_null_previous(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, name, region, name_previous, region_previous "
            "FROM customers ORDER BY id"
        )
        assert len(rows) == 2
        for row in rows:
            assert row[3] is None
            assert row[4] is None

    async def test_second_run_shifts_current_to_previous(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t.run(RunRequest())).succeeded
        await source_pool.execute(
            "UPDATE customers SET region = ? WHERE id = ?",
            ("APAC", 1),
        )
        with Tapestry() as t2:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT id, region, region_previous FROM customers ORDER BY id"
        )
        alice = [r for r in rows if r[0] == 1][0]
        assert alice[1] == "APAC"
        assert alice[2] == "EU"
        bob = [r for r in rows if r[0] == 2][0]
        assert bob[1] == "US"
        assert bob[2] is None

    async def test_unchanged_row_not_modified(
        self, source_pool: SqlitePool, target_pool: SqlitePool
    ) -> None:
        with Tapestry() as t:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t.run(RunRequest())).succeeded
        with Tapestry() as t2:
            ScdType3PreviousValue(
                source_pool=source_pool,
                source_query="SELECT id, name, region FROM customers",
                target_pool=target_pool,
                target_table="customers",
                key_columns=("id",),
                tracked_columns=("name", "region"),
                _config=KnotConfig(id="scd3"),
            )
        assert (await t2.run(RunRequest())).succeeded
        rows = await target_pool.fetch_all(
            "SELECT name_previous FROM customers ORDER BY id"
        )
        for row in rows:
            assert row[0] is None
