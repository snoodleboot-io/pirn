"""Unit tests for :class:`DuckdbPool`."""

from __future__ import annotations
import unittest
import tempfile
from pathlib import Path


try:
    import duckdb
except ImportError as _e:
    raise unittest.SkipTest("duckdb not installed") from _e

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.duckdb_config import DuckdbConfig
from pirn.domains.connectors.databases.duckdb_pool import DuckdbPool



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        assert isinstance(pool, DatabaseConnectionPool)
    
    
class TestCrud(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = DuckdbPool(DuckdbConfig(database=":memory:"))
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_create_insert_select(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE t (id INTEGER, name VARCHAR)")
        await pool.execute("INSERT INTO t VALUES (?, ?)", (1, "alice"))
        await pool.execute("INSERT INTO t VALUES (?, ?)", (2, "bob"))
        rows = await pool.fetch_all("SELECT id, name FROM t ORDER BY id")
        assert rows == [(1, "alice"), (2, "bob")]

    async def test_aggregations(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE n (x INTEGER)")
        for i in range(1, 11):
            await pool.execute("INSERT INTO n VALUES (?)", (i,))
        rows = await pool.fetch_all("SELECT SUM(x), AVG(x) FROM n")
        assert rows == [(55, 5.5)]


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {value}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")


class TestInjectionResistance(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = DuckdbPool(DuckdbConfig(database=":memory:"))
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_quote_in_value_is_treated_as_data(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE u (name VARCHAR)")
        evil = "alice'); DROP TABLE u; --"
        await pool.execute("INSERT INTO u VALUES (?)", (evil,))
        rows = await pool.fetch_all("SELECT name FROM u")
        assert rows == [(evil,)]


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_acquire_after_close_raises(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_is_idempotent(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        await pool.execute("CREATE TABLE t (x INT)")
        await pool.close()
        await pool.close()

    async def test_read_only_blocks_writes(self) -> None:
        _td_test_read_only_blocks_writes = tempfile.TemporaryDirectory()
        self.addCleanup(_td_test_read_only_blocks_writes.cleanup)
        tmp_path = Path(_td_test_read_only_blocks_writes.name)
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
        with self.assertRaises(Exception):  # noqa: BLE001 — DuckDB raises a specific error class
            await ro_pool.execute("INSERT INTO t VALUES (?)", (2,))
        await ro_pool.close()
