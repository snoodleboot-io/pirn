"""Unit tests for :class:`DuckdbPool`."""

from __future__ import annotations

import pytest

duckdb = pytest.importorskip("duckdb")

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.duckdb_config import DuckdbConfig
from pirn.domains.connectors.databases.duckdb_pool import DuckdbPool


@pytest.fixture
async def pool() -> DuckdbPool:
    p = DuckdbPool(DuckdbConfig(database=":memory:"))
    yield p
    await p.close()


def test_implements_database_connection_pool() -> None:
    pool = DuckdbPool(DuckdbConfig(database=":memory:"))
    assert isinstance(pool, DatabaseConnectionPool)


@pytest.mark.asyncio
class TestCrud:
    async def test_create_insert_select(self, pool: DuckdbPool) -> None:
        await pool.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
        await pool.execute("INSERT INTO t VALUES (?, ?)", (1, "alice"))
        await pool.execute("INSERT INTO t VALUES (?, ?)", (2, "bob"))
        rows = await pool.fetch_all("SELECT id, name FROM t ORDER BY id")
        assert rows == [(1, "alice"), (2, "bob")]

    async def test_aggregations(self, pool: DuckdbPool) -> None:
        await pool.execute("CREATE TABLE n (x INTEGER)")
        for i in range(1, 11):
            await pool.execute("INSERT INTO n VALUES (?)", (i,))
        rows = await pool.fetch_all("SELECT SUM(x), AVG(x) FROM n")
        assert rows == [(55, 5.5)]


class TestQuerySafety:
    def test_rejects_fstring_placeholder(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {value}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        with pytest.raises(ValueError, match="interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")


@pytest.mark.asyncio
class TestInjectionResistance:
    async def test_quote_in_value_is_treated_as_data(self, pool: DuckdbPool) -> None:
        await pool.execute("CREATE TABLE u (name VARCHAR)")
        evil = "alice'); DROP TABLE u; --"
        await pool.execute("INSERT INTO u VALUES (?)", (evil,))
        rows = await pool.fetch_all("SELECT name FROM u")
        assert rows == [(evil,)]


@pytest.mark.asyncio
class TestLifecycle:
    async def test_acquire_after_close_raises(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        await pool.close()
        with pytest.raises(RuntimeError, match="closed"):
            await pool.acquire()

    async def test_close_is_idempotent(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        await pool.execute("CREATE TABLE t (x INT)")
        await pool.close()
        await pool.close()

    async def test_read_only_blocks_writes(self, tmp_path) -> None:
        # Create a writable db with a table first.
        write_pool = DuckdbPool(DuckdbConfig(database=tmp_path / "ro.duckdb"))
        await write_pool.execute("CREATE TABLE t (x INT)")
        await write_pool.execute("INSERT INTO t VALUES (?)", (1,))
        await write_pool.close()

        ro_pool = DuckdbPool(
            DuckdbConfig(database=tmp_path / "ro.duckdb", read_only=True)
        )
        # Reads work.
        rows = await ro_pool.fetch_all("SELECT x FROM t")
        assert rows == [(1,)]
        # Writes are rejected by DuckDB.
        with pytest.raises(Exception):  # noqa: BLE001 — DuckDB raises a specific error class
            await ro_pool.execute("INSERT INTO t VALUES (?)", (2,))
        await ro_pool.close()
