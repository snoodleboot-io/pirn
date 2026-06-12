"""Unit tests for :class:`SqlitePool`.

Covers:
- Protocol conformance (DatabaseConnectionPool)
- Basic CRUD against in-memory SQLite
- Parameterized-query safety: rejects f-string / %-format markers
- Defence against SQL injection by-design (parameters travel separately)
- Idempotent close
"""

from __future__ import annotations

import unittest

try:
    import aiosqlite  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("aiosqlite not installed") from _e

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool

# ─────────────────────────────────────────────────────────────── fixtures


# ────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        assert isinstance(pool, DatabaseConnectionPool)
    
    
# ─────────────────────────────────────────────────────────────── CRUD


class TestCrud(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_create_insert_select(self) -> None:
        pool = self.pool
        await pool.execute(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)"
        )
        await pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (1, "alice"))
        await pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))

        rows = await pool.fetch_all("SELECT id, name FROM users ORDER BY id")
        assert rows == [(1, "alice"), (2, "bob")]

    async def test_execute_many_inserts_batch(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE k (k TEXT, v INT)")
        await pool.execute_many(
            "INSERT INTO k VALUES (?, ?)", [("a", 1), ("b", 2), ("c", 3)]
        )
        rows = await pool.fetch_all("SELECT k, v FROM k ORDER BY k")
        assert rows == [("a", 1), ("b", 2), ("c", 3)]


# ──────────────────────────────────────────────────── parameterized-query safety


class TestQuerySafety(unittest.TestCase):
    """The connector must refuse queries that show signs of in-line
    interpolation so the only path to user input is via the parameters arg."""

    def test_rejects_fstring_placeholder(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {value}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_qmark_placeholder(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        # No raise.
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = ?")


class TestInjectionResistance(unittest.IsolatedAsyncioTestCase):
    """Demonstrate that parameterized queries are the safe path: a malicious
    value does not end the query early or smuggle additional statements."""

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        

    async def test_quote_in_value_does_not_break_query(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE u (name TEXT)")
        evil = "alice'); DROP TABLE u; --"
        await pool.execute("INSERT INTO u (name) VALUES (?)", (evil,))
        rows = await pool.fetch_all("SELECT name FROM u")
        # The quote was treated as data, not query syntax.
        assert rows == [(evil,)]

    async def test_execute_through_pool_rejects_format_query(self) -> None:
        pool = self.pool
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", ())


# ────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        p = SqlitePool(SqliteConfig(database=":memory:"))
        self.pool = p

    async def asyncTearDown(self) -> None:
        await self.pool.close()
        
        
    async def test_acquire_after_close_raises(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()

    async def test_close_is_idempotent(self) -> None:
        pool = SqlitePool(SqliteConfig(database=":memory:"))
        await pool.execute("CREATE TABLE t (x INT)")
        await pool.close()
        await pool.close()  # second call must not raise

    async def test_release_is_noop_for_single_connection(self) -> None:
        pool = self.pool
        conn = await pool.acquire()
        await pool.release(conn)
        # Connection is still usable after release.
        await pool.execute("CREATE TABLE t (x INT)")
