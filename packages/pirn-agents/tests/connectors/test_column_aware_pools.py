"""Tests for the column-aware core-pool subclasses (PIR-693).

``ColumnAwareSqlitePool`` / ``ColumnAwarePostgresPool`` reuse core's pooling and
its ``_reject_inline_interpolation`` injection guard, adding only column-aware
reads. Offline: an injected connection (sqlite) / pool (postgres) makes
``acquire`` return the double without opening a real backend.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from typing import Any

import pytest
from pirn.connectors.databases.sqlite_config import SqliteConfig

from pirn_agents.connectors.column_aware_postgres_pool import ColumnAwarePostgresPool
from pirn_agents.connectors.column_aware_sqlite_pool import ColumnAwareSqlitePool


class _FakeCursor:
    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self.description = [(name,) for name in columns]
        self._rows = rows
        self.closed = False

    async def fetchall(self) -> Sequence[Sequence[Any]]:
        return self._rows

    async def close(self) -> None:
        self.closed = True


class _FakeAiosqliteConnection:
    """A double that models ``sqlite3``'s implicit-transaction rule.

    ``sqlite3`` opens a transaction for DML only — not for reads or DDL — and
    ``in_transaction`` reports it. ``ColumnAwareSqlitePool`` reads that flag to tell
    the transaction it opened from one the caller already had (PIR-801), so the
    double has to carry it or it would not exercise the real code path.
    """

    def __init__(self, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> None:
        self._columns = columns
        self._rows = rows
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self.commits = 0
        self.rollbacks = 0
        self.in_transaction = False

    def _make_cursor(self) -> _FakeCursor:
        return _FakeCursor(self._columns, self._rows)

    async def execute(self, query: str, parameters: tuple[Any, ...]) -> _FakeCursor:
        self.calls.append((query, parameters))
        if query.lstrip().split(" ")[0].upper() in ("INSERT", "UPDATE", "DELETE", "REPLACE"):
            self.in_transaction = True
        return self._make_cursor()

    async def commit(self) -> None:
        self.commits += 1
        self.in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self.in_transaction = False

    async def close(self) -> None:
        return None


class _ExplodingCursor(_FakeCursor):
    async def fetchall(self) -> Sequence[Sequence[Any]]:
        raise RuntimeError("backend blew up mid-statement")


class _ExplodingConnection(_FakeAiosqliteConnection):
    def _make_cursor(self) -> _FakeCursor:
        return _ExplodingCursor(self._columns, self._rows)


def _sqlite_pool(columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> ColumnAwareSqlitePool:
    conn = _FakeAiosqliteConnection(columns, rows)
    return ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]


class TestColumnAwareSqlitePool:
    async def test_fetch_columns_returns_columns_and_rows(self) -> None:
        pool = _sqlite_pool(["id", "name"], [[1, "a"], [2, "b"]])
        columns, rows = await pool.fetch_columns("SELECT id, name FROM t")
        assert columns == ["id", "name"]
        assert rows == [[1, "a"], [2, "b"]]

    async def test_parameters_are_bound_not_interpolated(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("SELECT id FROM t WHERE id = ?", [42])
        assert conn.calls[0] == ("SELECT id FROM t WHERE id = ?", (42,))

    async def test_like_and_json_literals_are_accepted(self) -> None:
        # Regression (PIR-693): core's inline-interpolation guard rejects literal
        # % and {} — common in LLM-authored reads — so it is deliberately not
        # applied. LIKE '%term%' and JSON braces must pass through as data.
        conn = _FakeAiosqliteConnection(["n"], [["x"]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("SELECT n FROM t WHERE n LIKE '%smith%'")
        await pool.fetch_columns("SELECT n FROM t WHERE j = '{\"k\": 1}'")
        assert [c[0] for c in conn.calls] == [
            "SELECT n FROM t WHERE n LIKE '%smith%'",
            "SELECT n FROM t WHERE j = '{\"k\": 1}'",
        ]


class TestSqlitePoolDurability:
    """Regression (PIR-801): ``fetch_columns`` must not leave a write uncommitted.

    Core's ``SqlitePool.execute`` commits; ``fetch_columns`` did not, so a statement
    routed through it (the only path ``SqlServiceConnector`` has) was rolled back
    when the connection closed. ``ColumnAwarePostgresPool`` has no matching bug —
    asyncpg autocommits outside an explicit transaction — so committing here also
    makes the two ``ColumnAwarePool`` implementations agree.
    """

    async def test_fetch_columns_commits(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("INSERT INTO t (id) VALUES (?)", [1])
        assert conn.commits == 1

    async def test_a_failed_statement_is_not_committed(self) -> None:
        conn = _ExplodingConnection(["id"], [[1]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        with pytest.raises(RuntimeError, match="blew up"):
            await pool.fetch_columns("INSERT INTO t (id) VALUES (?)", [1])
        assert conn.commits == 0
        # It is not enough to skip the commit: the transaction the failed statement
        # opened must be ended, or the next call inherits its partial write.
        assert conn.rollbacks == 1
        assert conn.in_transaction is False

    async def test_a_read_neither_commits_nor_rolls_back(self) -> None:
        conn = _FakeAiosqliteConnection(["id"], [[1]])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("SELECT id FROM t")
        assert (conn.commits, conn.rollbacks) == (0, 0)

    async def test_ddl_neither_commits_nor_rolls_back(self) -> None:
        conn = _FakeAiosqliteConnection([], [])
        pool = ColumnAwareSqlitePool(SqliteConfig(database=":memory:"), connection=conn)  # pyright: ignore[reportCallIssue]
        await pool.fetch_columns("CREATE TABLE t (id INTEGER)")
        assert (conn.commits, conn.rollbacks) == (0, 0)

    async def test_a_write_survives_close_and_reopen(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "durable.db")

        writer = ColumnAwareSqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        await writer.fetch_columns("CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT)")
        await writer.fetch_columns("INSERT INTO widget (id, name) VALUES (?, ?)", [1, "sprocket"])
        await writer.close()

        reader = ColumnAwareSqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            columns, rows = await reader.fetch_columns("SELECT id, name FROM widget")
        finally:
            await reader.close()
        assert columns == ["id", "name"]
        assert rows == [[1, "sprocket"]]


class TestSqlitePoolTransactionOwnership:
    """Regression (PIR-801): ``fetch_columns`` must own only the transaction it opened.

    The PIR-801 commit was unconditional, which made every call commit whatever
    happened to be open on the shared connection — including a partial write left
    behind by a *failed* statement, and a transaction the caller opened themselves.
    These exercise a real aiosqlite file: the behaviour under test is SQLite's own
    (``OR FAIL`` keeps rows already changed; ``COMMIT`` upgrades to an exclusive
    lock), so a hand-written double cannot show it.
    """

    @staticmethod
    async def _seed(database: str) -> None:
        """Create ``widget`` with a UNIQUE name and three committed rows."""
        pool = ColumnAwareSqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            await pool.fetch_columns(
                "CREATE TABLE widget (id INTEGER PRIMARY KEY, name TEXT UNIQUE)"
            )
            for row_id, name in ((1, "a"), (2, "b"), (3, "c")):
                await pool.fetch_columns(
                    "INSERT INTO widget (id, name) VALUES (?, ?)", [row_id, name]
                )
        finally:
            await pool.close()

    @staticmethod
    def _rows_on_disk(database: str) -> list[tuple[Any, ...]]:
        """Read the table back with plain ``sqlite3`` — the durable truth."""
        with sqlite3.connect(database) as disk:
            return disk.execute("SELECT id, name FROM widget ORDER BY id").fetchall()

    async def test_a_failed_statement_leaves_no_durable_residue(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "residue.db")
        await self._seed(database)

        pool = ColumnAwareSqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            # ``UPDATE OR FAIL`` renames row 1, then hits the UNIQUE constraint on
            # row 2 and aborts — keeping row 1's change and leaving the transaction
            # open.
            with pytest.raises(sqlite3.IntegrityError):
                await pool.fetch_columns("UPDATE OR FAIL widget SET name = 'dup'")
            connection = await pool.acquire()
            assert connection.in_transaction is False, "the failed statement was not rolled back"

            # An innocent read that asked for nothing must not adopt the residue.
            await pool.fetch_columns("SELECT id, name FROM widget")
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_a_read_does_not_commit_a_caller_transaction(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "caller_txn.db")
        await self._seed(database)

        pool = ColumnAwareSqlitePool(SqliteConfig(database=database))  # pyright: ignore[reportCallIssue]
        try:
            # The caller drives the pool directly and opens a transaction.
            connection = await pool.acquire()
            cursor = await connection.execute("INSERT INTO widget (id, name) VALUES (4, 'd')")
            await cursor.close()
            assert connection.in_transaction is True

            await pool.fetch_columns("SELECT id, name FROM widget")
            assert connection.in_transaction is True, "the read committed the caller's transaction"

            await connection.rollback()
        finally:
            await pool.close()

        assert self._rows_on_disk(database) == [(1, "a"), (2, "b"), (3, "c")]

    async def test_a_read_is_not_locked_out_by_a_concurrent_reader(self, tmp_path: Any) -> None:
        pytest.importorskip("aiosqlite")
        database = str(tmp_path / "locked.db")
        await self._seed(database)

        # ``timeout`` only bounds how long the lock wait takes; the outcome —
        # rows versus OperationalError — does not depend on machine speed.
        pool = ColumnAwareSqlitePool(  # pyright: ignore[reportCallIssue]
            SqliteConfig(database=database, journal_mode="DELETE", timeout=0.1)
        )
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
            columns, rows = await pool.fetch_columns(
                "SELECT id, name FROM widget WHERE id = ?", [1]
            )
            assert columns == ["id", "name"]
            assert rows == [[1, "a"]]

            await connection.rollback()
        finally:
            reader.close()
            await pool.close()


class _FakeRecord:
    def __init__(self, mapping: dict[str, Any]) -> None:
        self._mapping = mapping

    def keys(self) -> Sequence[str]:
        return list(self._mapping.keys())

    def values(self) -> Sequence[Any]:
        return list(self._mapping.values())


class _FakeAsyncpgPool:
    def __init__(self, records: Sequence[_FakeRecord]) -> None:
        self._records = records
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def acquire(self) -> Any:
        return self

    async def release(self, _connection: Any) -> None:
        return None

    async def fetch(self, query: str, *parameters: Any) -> Sequence[_FakeRecord]:
        self.calls.append((query, parameters))
        return self._records

    async def close(self) -> None:
        return None


class TestColumnAwarePostgresPool:
    async def test_fetch_columns_maps_records(self) -> None:
        records = [_FakeRecord({"id": 1, "name": "a"}), _FakeRecord({"id": 2, "name": "b"})]
        pool = ColumnAwarePostgresPool(pool=_FakeAsyncpgPool(records))
        columns, rows = await pool.fetch_columns("SELECT id, name FROM t WHERE id > $1", [0])
        assert columns == ["id", "name"]
        assert rows == [[1, "a"], [2, "b"]]

    async def test_empty_result_has_no_columns(self) -> None:
        pool = ColumnAwarePostgresPool(pool=_FakeAsyncpgPool([]))
        columns, rows = await pool.fetch_columns("SELECT id FROM t")
        assert columns == []
        assert rows == []

    async def test_like_literal_is_accepted(self) -> None:
        # Regression (PIR-693): '%s' in LIKE '%sale%' is data, not a bind marker.
        fake = _FakeAsyncpgPool([_FakeRecord({"n": "x"})])
        pool = ColumnAwarePostgresPool(pool=fake)
        await pool.fetch_columns("SELECT n FROM t WHERE n LIKE '%sale%'")
        assert fake.calls[0][0] == "SELECT n FROM t WHERE n LIKE '%sale%'"
