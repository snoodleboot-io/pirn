"""Unit tests for :class:`MssqlPool`.

Uses an injected stub aioodbc-shaped pool — no real ODBC driver / SQL
Server installation needed.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.mssql_config import MssqlConfig
from pirn.connectors.databases.mssql_pool import MssqlPool

# ──────────────────────────────────────────────────────────── fake pool


class FakeMssqlCursor:
    def __init__(
        self, parent: FakeMssqlConnection
    ) -> None:
        self._parent = parent
        self._last_query: str | None = None
        self.rowcount = 0
        self.closed = False

    async def execute(self, query: str, params: list[Any]) -> None:
        self._parent.parent_pool.executed.append((query, list(params)))
        self._last_query = query
        self.rowcount = 1

    async def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._parent.parent_pool.executed_many.append(
            (query, [list(r) for r in rows])
        )
        self.rowcount = len(rows)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return self._parent.parent_pool.responses.get(self._last_query or "", [])

    async def close(self) -> None:
        self.closed = True


class FakeMssqlConnection:
    def __init__(self, parent_pool: FakeAioodbcPool) -> None:
        self.parent_pool = parent_pool
        self.committed = 0

    async def cursor(self) -> FakeMssqlCursor:
        return FakeMssqlCursor(self)

    async def commit(self) -> None:
        self.committed += 1


class FakeAioodbcPool:
    """Mirrors ``aioodbc.Pool`` surface."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.acquired: list[FakeMssqlConnection] = []
        self.released: list[FakeMssqlConnection] = []
        self.closed = False
        self.waited = False

    async def acquire(self) -> FakeMssqlConnection:
        conn = FakeMssqlConnection(self)
        self.acquired.append(conn)
        return conn

    async def release(self, conn: FakeMssqlConnection) -> None:
        self.released.append(conn)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            MssqlPool()
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.execute("INSERT INTO t (x) VALUES (?)", [1])
        assert fake.executed == [("INSERT INTO t (x) VALUES (?)", [1])]
        # connection acquired and released
        assert len(fake.acquired) == 1
        assert fake.released == fake.acquired

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAioodbcPool()
        fake.responses["SELECT id FROM t WHERE x = ?"] = [(1,), (2,)]
        pool = MssqlPool(pool=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = ?", [99])
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (?, ?)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (?, ?)", [[1, "a"], [2, "b"]])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_qmark_placeholder(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = ?")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAioodbcPool()
        pool = MssqlPool(pool=fake)
        await pool.close()
        assert fake.closed is True
        assert fake.waited is True

    async def test_close_is_idempotent(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = MssqlPool(pool=FakeAioodbcPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["host"] == "db.example.com"

    def test_build_dsn_constructs_from_fields(self) -> None:
        cfg = MssqlConfig(
            host="db.example.com",
            port=1433,
            user="alice",
            password="pw",
            database="prod",
            driver="ODBC Driver 18 for SQL Server",
        )
        dsn = cfg.build_dsn()
        assert f"SERVER={cfg.host},{cfg.port}" in dsn
        assert "DATABASE=prod" in dsn
        assert "UID=alice" in dsn
        assert "PWD=pw" in dsn

    def test_build_dsn_returns_explicit_dsn_verbatim(self) -> None:
        provided = "DRIVER={ODBC Driver 18 for SQL Server};SERVER=x;UID=u;PWD=p;"
        cfg = MssqlConfig(dsn=provided)
        assert cfg.build_dsn() == provided


# ──────────────────────────────────────────────────── transaction ownership
#
# The doubles below model aioodbc/pyodbc transaction semantics rather than
# just their method names, so the ownership guarantee can be exercised
# offline (no SQL Server and no aioodbc install is available here). Each
# behaviour was read off the aioodbc 0.5.0 sources:
#
# * ``Pool.release()`` neither rolls back nor inspects transaction state — it
#   appends the connection straight back onto the free list (``pool.py``), so
#   work a caller abandoned survives into the next checkout. This is the
#   difference from aiomysql, whose release() destroys such a connection.
# * ``Connection`` exposes ``autocommit``, ``commit()`` and ``rollback()``
#   and *no* in-transaction flag (``connection.py``) — pyodbc has no
#   equivalent of ``sqlite3.Connection.in_transaction``.
# * With ``autocommit=False`` ODBC opens a transaction implicitly at the
#   first statement after connect/commit/rollback, a ``SELECT`` included.


class FakeMssqlServer:
    """Durable state shared by every connection the fake pool hands out."""

    def __init__(self) -> None:
        self.durable: list[str] = []


class TransactionalMssqlCursor:
    """Cursor whose statements drive :class:`TransactionalMssqlConnection`."""

    def __init__(self, connection: TransactionalMssqlConnection) -> None:
        self._connection = connection
        self.rowcount = 0
        self.closed = False

    async def execute(self, query: str, params: list[Any]) -> None:
        self._connection.run_statement(query)
        self.rowcount = 1

    async def executemany(self, query: str, rows: list[list[Any]]) -> None:
        for _ in rows:
            self._connection.run_statement(query)
        self.rowcount = len(rows)

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return [(token,) for token in self._connection.visible_rows()]

    async def close(self) -> None:
        self.closed = True


class TransactionalMssqlConnection:
    """aioodbc-shaped connection with ODBC implicit-transaction behaviour.

    Statement grammar used by the tests:

    * ``INSERT <token>`` — a write; durable only once committed.
    * ``FAIL <token>`` — a write that keeps what it already changed and then
      raises, leaving the transaction open.
    * anything else — a read.

    Deliberately exposes no in-transaction flag, because pyodbc has none.
    """

    def __init__(self, server: FakeMssqlServer, *, autocommit: bool = True) -> None:
        self._server = server
        self.autocommit = autocommit
        self._pending: list[str] = []
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    def visible_rows(self) -> list[str]:
        return [*self._server.durable, *self._pending]

    @property
    def pending(self) -> list[str]:
        return list(self._pending)

    def run_statement(self, query: str) -> None:
        verb, _, token = query.partition(" ")
        if verb == "INSERT":
            self._write(token)
        elif verb == "FAIL":
            self._write(token)
            raise RuntimeError("mssql: statement aborted part-way")

    def _write(self, token: str) -> None:
        if self.autocommit:
            self._server.durable.append(token)
        else:
            self._pending.append(token)

    async def cursor(self) -> TransactionalMssqlCursor:
        return TransactionalMssqlCursor(self)

    async def commit(self) -> None:
        self.commits += 1
        self._server.durable.extend(self._pending)
        self._pending.clear()

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._pending.clear()


class TransactionalAioodbcPool:
    """Fake ``aioodbc.Pool``: release() returns the connection untouched."""

    def __init__(self, *, autocommit: bool = True) -> None:
        self.server = FakeMssqlServer()
        self.autocommit = autocommit
        self.created: list[TransactionalMssqlConnection] = []
        self._free: list[TransactionalMssqlConnection] = []

    @property
    def free(self) -> list[TransactionalMssqlConnection]:
        return list(self._free)

    async def acquire(self) -> TransactionalMssqlConnection:
        if self._free:
            return self._free.pop()
        conn = TransactionalMssqlConnection(self.server, autocommit=self.autocommit)
        self.created.append(conn)
        return conn

    async def release(self, conn: TransactionalMssqlConnection) -> None:
        # aioodbc/pool.py: no rollback, no transaction check — straight back
        # onto the free list.
        self._free.append(conn)


class TestTransactionOwnership(unittest.IsolatedAsyncioTestCase):
    async def test_execute_does_not_commit_abandoned_work(self) -> None:
        # A caller drives the public acquire/release pair, leaves DML
        # uncommitted, and the same connection is handed to a later execute().
        # That later, unrelated statement must not make the abandoned work
        # durable.
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        connection = await pool.acquire()
        connection.run_statement("INSERT abandoned")
        await pool.release(connection)

        await pool.execute("INSERT unrelated")

        assert "abandoned" not in fake.server.durable
        assert fake.server.durable == ["unrelated"]

    async def test_release_discards_uncommitted_work(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        connection = await pool.acquire()
        connection.run_statement("INSERT abandoned")
        await pool.release(connection)

        assert connection.pending == []
        assert fake.server.durable == []

    async def test_write_survives(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        await pool.execute("INSERT alpha")

        assert fake.server.durable == ["alpha"]

    async def test_execute_many_write_survives(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        await pool.execute_many("INSERT beta", [(1,), (2,)])

        assert fake.server.durable == ["beta", "beta"]

    async def test_failed_statement_leaves_no_residue(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        with self.assertRaisesRegex(RuntimeError, "aborted part-way"):
            await pool.execute("FAIL ghost")

        assert fake.created[0].rollbacks == 1
        assert fake.server.durable == []

        # And the residue must not resurface on the next statement, which
        # gets the very same connection back from aioodbc's free list.
        await pool.execute("INSERT later")
        assert fake.server.durable == ["later"]

    async def test_read_leaves_no_open_transaction(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        await pool.execute("INSERT alpha")
        await pool.fetch_all("SELECT x FROM t")

        # The SELECT opened a transaction under autocommit=False; ending it is
        # what stops the connection going back to the pool mid-transaction.
        connection = fake.created[0]
        assert connection.commits == 2
        assert connection.pending == []

    async def test_failed_read_rolls_back(self) -> None:
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)

        with self.assertRaisesRegex(RuntimeError, "aborted part-way"):
            await pool.fetch_all("FAIL ghost")

        assert fake.created[0].rollbacks == 1
        assert fake.server.durable == []

    async def test_release_returns_connection_even_if_rollback_fails(self) -> None:
        # A dead connection must not cost the caller the checkout as well.
        fake = TransactionalAioodbcPool(autocommit=False)
        pool = MssqlPool(pool=fake)
        connection = await pool.acquire()

        async def exploding_rollback() -> None:
            raise RuntimeError("mssql: connection is dead")

        connection.rollback = exploding_rollback  # type: ignore[method-assign]

        with self.assertRaisesRegex(RuntimeError, "connection is dead"):
            await pool.release(connection)

        assert fake.free == [connection]

    async def test_autocommit_session_needs_no_transaction_control(self) -> None:
        # MssqlConfig.autocommit defaults to True: ODBC commits each statement
        # itself, so the pool must not add round-trips of its own.
        fake = TransactionalAioodbcPool(autocommit=True)
        pool = MssqlPool(pool=fake)

        await pool.execute("INSERT gamma")
        await pool.fetch_all("SELECT x FROM t")
        connection = await pool.acquire()
        await pool.release(connection)

        assert fake.server.durable == ["gamma"]
        assert fake.created[0].commits == 0
        assert fake.created[0].rollbacks == 0
