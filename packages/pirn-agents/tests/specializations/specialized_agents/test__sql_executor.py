"""Unit tests for :class:`_SQLExecutor`."""

from __future__ import annotations

import sqlite3
import unittest
from typing import Any

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.specialized_agents._sql_executor import (
    _SQLExecutor,
)
from tests.specializations.conftest import (
    StubDatabaseConnectionPool,
)


class _SqlSource(Knot):
    def __init__(self, sql, *, _config, **kwargs):
        self._sql = sql
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any):
        return self._sql


class TestSQLExecutorProcess(unittest.IsolatedAsyncioTestCase):
    async def test_executes_query_and_returns_rows(self) -> None:
        pool = StubDatabaseConnectionPool(rows=[(1, "Alice"), (2, "Bob")])
        with Tapestry() as t:
            src = _SqlSource("SELECT id, name FROM users", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        rows = result.outputs["ex"]
        assert rows == [(1, "Alice"), (2, "Bob")]

    async def test_rejects_empty_sql(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry() as t:
            src = _SqlSource("", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        assert not result.succeeded

    async def test_rejects_inline_interpolation(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry() as t:
            src = _SqlSource("SELECT * FROM t WHERE x = {value}", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        assert not result.succeeded


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_process_rejects_empty_sql(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry():
            k = _SQLExecutor.__new__(_SQLExecutor)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        with self.assertRaises(ValueError):
            await k.process(sql="", pool=pool)


def _build(sql: str, pool: Any, *, read_only: bool = True) -> _SQLExecutor:
    """Construct a configured ``_SQLExecutor`` outside any enclosing run."""
    with Tapestry():
        return _SQLExecutor(
            sql=sql,
            pool=pool,
            read_only=read_only,
            _config=KnotConfig(id="ex"),
        )


class TestSQLExecutorIsReadOnlyByDefault:
    """Regression (PIR-817): model-generated SQL ran with no read-only guard.

    ``_SQLExecutor`` is the only consumer of :class:`SQLAgent`'s LLM-written
    statement, and its sole check was ``_reject_inline_interpolation`` — an
    *injection* guard, which stops the model splicing values into statement
    text and says nothing about the model emitting ``DROP TABLE``. Every other
    SQL path in the package gained :class:`ReadOnlySqlGuard` (PIR-801,
    PIR-807); this one was missed because it lives under ``specializations/``
    rather than ``tools/sql/`` or ``connectors/``.
    """

    @pytest.mark.parametrize(
        "sql",
        [
            "DROP TABLE users",
            "DELETE FROM users",
            "UPDATE users SET name = 'x'",
            "INSERT INTO users (id) VALUES (1)",
            "CREATE TABLE t (id INTEGER)",
            "ALTER TABLE users ADD COLUMN x TEXT",
            "TRUNCATE TABLE users",
            "ATTACH DATABASE 'evil.db' AS evil",
            "PRAGMA journal_mode = WAL",
        ],
    )
    async def test_rejects_writes_and_ddl_by_default(self, sql: str) -> None:
        pool = StubDatabaseConnectionPool()
        executor = _build(sql, pool)
        with pytest.raises(ValueError):
            await executor.process(sql=sql, pool=pool)
        # Rejected before the statement could reach the database, not after.
        assert pool.queries == []

    async def test_rejects_select_into_by_default(self) -> None:
        """The PIR-812 tightening must reach this path too.

        ``SELECT ... INTO`` begins with ``SELECT`` and names no write keyword,
        yet it creates a table on PostgreSQL and writes a file on MySQL.
        """
        pool = StubDatabaseConnectionPool()
        sql = "SELECT * INTO copied FROM users"
        executor = _build(sql, pool)
        with pytest.raises(ValueError):
            await executor.process(sql=sql, pool=pool)
        assert pool.queries == []

    async def test_allows_a_plain_read_by_default(self) -> None:
        pool = StubDatabaseConnectionPool(rows=[(1, "Alice")])
        sql = "SELECT id, name FROM users"
        executor = _build(sql, pool)
        assert await executor.process(sql=sql, pool=pool) == [(1, "Alice")]
        assert pool.queries == [sql]

    async def test_a_write_is_refused_through_the_full_tapestry_run(self) -> None:
        pool = StubDatabaseConnectionPool()
        with Tapestry() as t:
            src = _SqlSource("DROP TABLE users", _config=KnotConfig(id="sql"))
            _SQLExecutor(sql=src, pool=pool, _config=KnotConfig(id="ex"))
        result = await t.run(RunRequest())
        assert not result.succeeded
        assert pool.queries == []

    async def test_a_write_still_needs_the_interpolation_guard(self) -> None:
        """``read_only=False`` opts out of the read guard only — not the other one.

        The two guards defend different threats: ``ReadOnlySqlGuard`` limits
        what the statement may *do*, ``_reject_inline_interpolation`` limits
        how its values got there. Opting in to writes must not disarm the
        injection guard.
        """
        pool = StubDatabaseConnectionPool()
        sql = "INSERT INTO t (x) VALUES ({value})"
        executor = _build(sql, pool, read_only=False)
        with pytest.raises(ValueError):
            await executor.process(sql=sql, pool=pool)
        assert pool.queries == []


class TestSQLExecutorWriteDurability:
    """Regression (PIR-817): a permitted write was routed through a path that never commits.

    ``_SQLExecutor`` preferred ``pool.fetch_all``, and core's
    ``SqlitePool.fetch_all`` — unlike its ``execute`` — issues no ``COMMIT``.
    A write therefore vanished when the connection closed, silently and with
    no error, the same shape PIR-801 fixed for ``fetch_columns``. The path both
    bypassed read-only *and* lost writes: neither the safe nor the useful
    behaviour was delivered.
    """

    @staticmethod
    def _rows_on_disk(database: str) -> list[tuple[Any, ...]]:
        """Read the table back with plain ``sqlite3`` — the durable truth."""
        with sqlite3.connect(database) as disk:
            return disk.execute("SELECT id, name FROM widget ORDER BY id").fetchall()

    @staticmethod
    async def _seed(database: str) -> None:
        """Create ``widget`` with a UNIQUE name and three committed rows."""
        pool = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            await pool.execute("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
            for row_id, name in ((1, "a"), (2, "b"), (3, "c")):
                await pool.execute(
                    "INSERT INTO widget (id, name) VALUES (?, ?)",
                    (row_id, name),
                )
        finally:
            await pool.close()

    async def test_a_permitted_write_survives_close_and_reopen(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "durable.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        sql = "INSERT INTO widget (id, name) VALUES (4, 'sprocket')"
        executor = _build(sql, pool, read_only=False)
        try:
            await executor.process(sql=sql, pool=pool)
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [
            (1, "a"),
            (2, "b"),
            (3, "c"),
            (4, "sprocket"),
        ]

    async def test_a_failed_statement_leaves_no_durable_residue(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "residue.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        # ``UPDATE OR FAIL`` renames row 1, then hits the UNIQUE constraint on
        # row 2 and aborts — keeping row 1's change and leaving the transaction
        # open. Without a rollback that partial write survives to be committed
        # by whatever runs next, including a pure read.
        sql = "UPDATE OR FAIL widget SET name = 'dup'"
        executor = _build(sql, pool, read_only=False)
        try:
            with pytest.raises(sqlite3.IntegrityError):
                await executor.process(sql=sql, pool=pool)
            connection = await pool.acquire()
            assert connection.in_transaction is False, "the failed statement was not rolled back"
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_a_read_does_not_commit_a_caller_transaction(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "caller_txn.db")
        await self._seed(database)

        pool = SqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        sql = "SELECT id, name FROM widget"
        executor = _build(sql, pool, read_only=False)
        try:
            # The caller drives the pool directly and opens a transaction.
            connection = await pool.acquire()
            cursor = await connection.execute("INSERT INTO widget (id, name) VALUES (4, 'd')")
            await cursor.close()
            assert connection.in_transaction is True

            await executor.process(sql=sql, pool=pool)
            assert connection.in_transaction is True, "the read committed the caller's transaction"

            await connection.rollback()
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]
