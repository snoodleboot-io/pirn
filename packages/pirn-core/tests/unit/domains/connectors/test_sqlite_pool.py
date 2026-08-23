"""Unit tests for :class:`SqlitePool`.

Covers:
- Protocol conformance (DatabaseConnectionPool)
- Basic CRUD against in-memory SQLite
- Parameterized-query safety: rejects f-string / %-format markers
- Defence against SQL injection by-design (parameters travel separately)
- Idempotent close
"""

from __future__ import annotations

import sqlite3
import unittest
from typing import Any

import pytest

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
        await pool.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        await pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (1, "alice"))
        await pool.execute("INSERT INTO users (id, name) VALUES (?, ?)", (2, "bob"))

        rows = await pool.fetch_all("SELECT id, name FROM users ORDER BY id")
        assert rows == [(1, "alice"), (2, "bob")]

    async def test_execute_many_inserts_batch(self) -> None:
        pool = self.pool
        await pool.execute("CREATE TABLE k (k TEXT, v INT)")
        await pool.execute_many("INSERT INTO k VALUES (?, ?)", [("a", 1), ("b", 2), ("c", 3)])
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


# ─────────────────────────────────────────────────── transaction ownership


class TestTransactionOwnership:
    """Regression (PIR-819): each call must own only the transaction it opened.

    ``execute``/``execute_many`` committed unconditionally and ``fetch_all``
    neither committed nor rolled back, which on this pool's single shared
    connection made the two defects compound: a DML statement run through
    ``fetch_all`` stranded its transaction, and the next ``execute`` — even a
    pure read — adopted and committed it. The same unconditional commit also
    committed a transaction the caller had opened themselves.

    This is the guarantee ``ColumnAwareSqlitePool.fetch_columns`` (PIR-801),
    ``AiosqliteConnector``/``SqliteConnector`` (PIR-807) and ``_SQLExecutor``
    (PIR-817) already make. These exercise a real aiosqlite file: the behaviour
    under test is SQLite's own (``OR FAIL`` keeps rows already changed;
    ``COMMIT`` upgrades to an exclusive lock), so a hand-written double cannot
    show it.
    """

    @staticmethod
    async def _seed(database: str) -> None:
        """Create ``widget`` with a UNIQUE name and three committed rows."""
        pool = SqlitePool(SqliteConfig(database=database))
        try:
            await pool.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
            await pool.execute_many(
                "INSERT INTO widget (id, name) VALUES (?, ?)",
                [(1, "a"), (2, "b"), (3, "c")],
            )
        finally:
            await pool.close()

    @staticmethod
    def _rows_on_disk(database: str) -> list[tuple[Any, ...]]:
        """Read the table back with plain ``sqlite3`` — the durable truth."""
        with sqlite3.connect(database) as disk:
            return disk.execute("SELECT id, name FROM widget ORDER BY id").fetchall()

    async def test_dml_through_fetch_all_leaves_no_open_transaction(self, tmp_path: Any) -> None:
        """A write that reaches ``fetch_all`` must be finished, not stranded."""
        database = str(tmp_path / "stranded.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))
        try:
            await pool.fetch_all("INSERT INTO widget (id, name) VALUES (4, 'd') RETURNING id")
            connection = await pool.acquire()
            assert connection.in_transaction is False, (
                "fetch_all stranded the transaction its own DML statement opened"
            )
        finally:
            await pool.close()

        # Owning it means committing it: the write is durable once fetch_all returns.
        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c"), (4, "d")]

    async def test_execute_does_not_commit_a_caller_transaction(self, tmp_path: Any) -> None:
        database = str(tmp_path / "caller_txn_execute.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))
        try:
            # The caller drives the pool directly and opens a transaction.
            connection = await pool.acquire()
            cursor = await connection.execute("INSERT INTO widget (id, name) VALUES (4, 'd')")
            await cursor.close()
            assert connection.in_transaction is True

            await pool.execute("SELECT id, name FROM widget")
            assert connection.in_transaction is True, "execute committed the caller's transaction"

            await connection.rollback()
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_execute_many_does_not_commit_a_caller_transaction(self, tmp_path: Any) -> None:
        database = str(tmp_path / "caller_txn_execute_many.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))
        try:
            connection = await pool.acquire()
            cursor = await connection.execute("INSERT INTO widget (id, name) VALUES (4, 'd')")
            await cursor.close()
            assert connection.in_transaction is True

            # ``executemany`` only accepts DML, so this joins the transaction the
            # caller already opened rather than starting one of its own — which
            # makes the caller, not this call, the one who may end it.
            await pool.execute_many(
                "INSERT INTO widget (id, name) VALUES (?, ?)", [(5, "e"), (6, "f")]
            )
            assert connection.in_transaction is True, (
                "execute_many committed the caller's transaction"
            )

            await connection.rollback()
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_a_failed_statement_leaves_no_durable_residue(self, tmp_path: Any) -> None:
        database = str(tmp_path / "residue.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))
        try:
            # ``UPDATE OR FAIL`` renames row 1, then hits the UNIQUE constraint on
            # row 2 and aborts — keeping row 1's change and leaving the transaction
            # open.
            with pytest.raises(sqlite3.IntegrityError):
                await pool.execute("UPDATE OR FAIL widget SET name = 'dup'")
            connection = await pool.acquire()
            assert connection.in_transaction is False, "the failed statement was not rolled back"

            # An innocent read that asked for nothing must not adopt the residue.
            await pool.fetch_all("SELECT id, name FROM widget")
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_a_read_is_not_locked_out_by_a_concurrent_reader(self, tmp_path: Any) -> None:
        """A read must issue no ``COMMIT`` — one would need the exclusive lock."""
        database = str(tmp_path / "locked.db")
        await self._seed(database)

        # ``timeout`` only bounds how long the lock wait takes; the outcome —
        # rows versus OperationalError — does not depend on machine speed.
        pool = SqlitePool(SqliteConfig(database=database, journal_mode="DELETE", timeout=0.1))
        reader = sqlite3.connect(database, timeout=0.1)
        try:
            # The caller holds an open write transaction (RESERVED).
            connection = await pool.acquire()
            cursor = await connection.execute("INSERT INTO widget (id, name) VALUES (4, 'd')")
            await cursor.close()

            # A second connection holds a shared read lock, which blocks the
            # exclusive lock a COMMIT needs under journal_mode=DELETE.
            reader.execute("BEGIN")
            reader.execute("SELECT id FROM widget").fetchall()

            # A pure read must still be a pure read.
            rows = await pool.fetch_all("SELECT id, name FROM widget WHERE id = ?", (1,))
            assert rows == [(1, "a")]

            await connection.rollback()
        finally:
            reader.close()
            await pool.close()
