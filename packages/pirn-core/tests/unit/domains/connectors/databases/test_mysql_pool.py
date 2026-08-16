"""Unit tests for :class:`MySQLPool`.

Uses an injected stub aiomysql-shaped pool — no real MySQL server or
aiomysql driver installation required.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.mysql_config import MySQLConfig
from pirn.connectors.databases.mysql_pool import MySQLPool

# ──────────────────────────────────────────────────────────── fake pool


class FakeMysqlCursor:
    def __init__(
        self, parent: FakeMysqlConnection
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


class FakeMysqlConnection:
    def __init__(self, parent_pool: FakeAiomysqlPool) -> None:
        self.parent_pool = parent_pool
        self.committed = 0

    async def cursor(self) -> FakeMysqlCursor:
        return FakeMysqlCursor(self)

    async def commit(self) -> None:
        self.committed += 1


class FakeAiomysqlPool:
    """Mirrors ``aiomysql.Pool`` surface."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.acquired: list[FakeMysqlConnection] = []
        self.released: list[FakeMysqlConnection] = []
        self.closed = False
        self.waited = False

    async def acquire(self) -> FakeMysqlConnection:
        conn = FakeMysqlConnection(self)
        self.acquired.append(conn)
        return conn

    async def release(self, conn: FakeMysqlConnection) -> None:
        self.released.append(conn)

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        self.waited = True


# ───────────────────────────────────────────────────────────── conformance



class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        assert isinstance(pool, DatabaseConnectionPool)
    
    
    def test_construction_requires_config_or_pool(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or pool="):
            MySQLPool()
    
    
    def test_construction_rejects_bogus_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "MySQLConfig"):
            MySQLPool(config="not-a-config")  # type: ignore[arg-type]
    
    
# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.execute(
            "INSERT INTO t (x, y) VALUES (%s, %s)", [1, "hello"]
        )
        assert fake.executed == [
            ("INSERT INTO t (x, y) VALUES (%s, %s)", [1, "hello"])
        ]
        # connection acquired and released
        assert len(fake.acquired) == 1
        assert fake.released == fake.acquired

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeAiomysqlPool()
        fake.responses["SELECT id FROM t WHERE x = %s"] = [(1,), (2,)]
        pool = MySQLPool(pool=fake)
        rows = await pool.fetch_all(
            "SELECT id FROM t WHERE x = %s", [99]
        )
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.execute_many(
            "INSERT INTO t VALUES (%s, %s)", [(1, "a"), (2, "b")]
        )
        assert fake.executed_many == [
            ("INSERT INTO t VALUES (%s, %s)", [[1, "a"], [2, "b"]])
        ]

    async def test_acquire_release_roundtrip(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        conn = await pool.acquire()
        await pool.release(conn)
        assert fake.acquired == [conn]
        assert fake.released == [conn]


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_accepts_percent_s_placeholder(self) -> None:
        # ``%s`` is the canonical MySQL placeholder, not interpolation.
        pool = MySQLPool(pool=FakeAiomysqlPool())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_brace_query(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT * FROM t WHERE x = {evil}", [])

    async def test_fetch_all_rejects_brace_query(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_pool(self) -> None:
        fake = FakeAiomysqlPool()
        pool = MySQLPool(pool=fake)
        await pool.close()
        assert fake.closed is True
        assert fake.waited is True

    async def test_close_is_idempotent(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = MySQLPool(pool=FakeAiomysqlPool())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = MySQLConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = MySQLConfig(
            host="db.example.com",
            user="alice",
            password="hunter2-leaks",
            database="prod",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["host"] == "db.example.com"
        assert d["user"] == "alice"

    def test_password_listed_in_sensitive_fields(self) -> None:
        assert "password" in MySQLConfig.sensitive_fields


# ──────────────────────────────────────────────────── transaction ownership
#
# The doubles below model aiomysql's transaction semantics rather than just
# its method names, so the ownership guarantee can be exercised offline
# (no MySQL server and no aiomysql install is available here). Each
# behaviour they reproduce was read off the aiomysql 0.3.2 sources:
#
# * ``Connection.get_transaction_status()`` returns
#   ``bool(server_status & SERVER_STATUS_IN_TRANS)`` — MySQL's own flag off
#   the last OK/EOF packet, not a client-side guess (``connection.py``).
# * ``Pool.release()`` samples that flag and, when set, calls ``conn.close()``
#   and drops the connection instead of returning it to the free list
#   (``pool.py``) — so a connection left mid-transaction is destroyed.
# * Under the aiomysql default ``autocommit=False``, InnoDB opens a
#   transaction for *any* first statement, a plain ``SELECT`` included.


class FakeMysqlServer:
    """Durable state shared by every connection the fake pool hands out."""

    def __init__(self) -> None:
        self.durable: list[str] = []


class TransactionalMysqlCursor:
    """Cursor whose statements drive :class:`TransactionalMysqlConnection`."""

    def __init__(self, connection: TransactionalMysqlConnection) -> None:
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


class TransactionalMysqlConnection:
    """aiomysql-shaped connection that tracks ``SERVER_STATUS_IN_TRANS``.

    Statement grammar used by the tests:

    * ``INSERT <token>`` — a write; lands in the durable set only on commit.
    * ``FAIL <token>`` — a write that keeps the row it already changed and
      then raises, leaving the transaction open. Models a statement that
      aborts part-way (MySQL's ``INSERT IGNORE``/mid-statement error), which
      is the case a rollback has to clean up.
    * anything else — a read.
    """

    def __init__(self, server: FakeMysqlServer, *, autocommit: bool = False) -> None:
        self._server = server
        self.autocommit_mode = autocommit
        self._in_transaction = False
        self._pending: list[str] = []
        self.closed = False
        self.commits = 0
        self.rollbacks = 0

    def get_transaction_status(self) -> bool:
        return self._in_transaction

    def visible_rows(self) -> list[str]:
        return [*self._server.durable, *self._pending]

    def run_statement(self, query: str) -> None:
        if not self.autocommit_mode:
            self._in_transaction = True
        verb, _, token = query.partition(" ")
        if verb == "INSERT":
            self._write(token)
        elif verb == "FAIL":
            self._write(token)
            raise RuntimeError("mysql: statement aborted part-way")

    def _write(self, token: str) -> None:
        if self.autocommit_mode:
            self._server.durable.append(token)
        else:
            self._pending.append(token)

    async def cursor(self) -> TransactionalMysqlCursor:
        return TransactionalMysqlCursor(self)

    async def commit(self) -> None:
        self.commits += 1
        self._server.durable.extend(self._pending)
        self._pending.clear()
        self._in_transaction = False

    async def rollback(self) -> None:
        self.rollbacks += 1
        self._pending.clear()
        self._in_transaction = False


class TransactionalAiomysqlPool:
    """Fake ``aiomysql.Pool`` that reproduces ``release()``'s discard rule."""

    def __init__(self, *, autocommit: bool = False) -> None:
        self.server = FakeMysqlServer()
        self.autocommit = autocommit
        self.created: list[TransactionalMysqlConnection] = []
        self.discarded: list[TransactionalMysqlConnection] = []
        self._free: list[TransactionalMysqlConnection] = []

    async def acquire(self) -> TransactionalMysqlConnection:
        if self._free:
            return self._free.pop()
        conn = TransactionalMysqlConnection(self.server, autocommit=self.autocommit)
        self.created.append(conn)
        return conn

    async def release(self, conn: TransactionalMysqlConnection) -> None:
        # aiomysql/pool.py: a connection still in a transaction is closed and
        # dropped rather than reused.
        if conn.get_transaction_status():
            conn.closed = True
            self.discarded.append(conn)
            return
        self._free.append(conn)


class PreDirtiedMysqlPool(TransactionalAiomysqlPool):
    """Hands out a connection that already has a transaction open.

    A real ``aiomysql.Pool`` never does this — its ``release()`` discards such
    a connection. It is reachable through ``MySQLPool(pool=...)``, whose
    injected-pool seam accepts any pool-shaped object, and it is what pins
    down that the ownership check reads the connection rather than assuming
    a clean checkout.
    """

    async def acquire(self) -> TransactionalMysqlConnection:
        conn = await super().acquire()
        conn.run_statement("INSERT caller-work")
        return conn


class TestTransactionOwnership(unittest.IsolatedAsyncioTestCase):
    async def test_write_survives(self) -> None:
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        await pool.execute("INSERT alpha")

        assert fake.server.durable == ["alpha"]

    async def test_execute_many_write_survives(self) -> None:
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        await pool.execute_many("INSERT beta", [(1,), (2,)])

        assert fake.server.durable == ["beta", "beta"]

    async def test_read_leaves_no_open_transaction(self) -> None:
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        await pool.fetch_all("SELECT x FROM t")

        connection = fake.created[0]
        assert connection.get_transaction_status() is False
        assert fake.discarded == []

    async def test_read_does_not_churn_connections(self) -> None:
        # A read that returns its connection mid-transaction is destroyed by
        # aiomysql's release(), so every read would pay a fresh connect.
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        await pool.fetch_all("SELECT x FROM t")
        await pool.fetch_all("SELECT x FROM t")
        await pool.fetch_all("SELECT x FROM t")

        assert len(fake.created) == 1
        assert fake.discarded == []

    async def test_failed_statement_leaves_no_residue(self) -> None:
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        with self.assertRaisesRegex(RuntimeError, "aborted part-way"):
            await pool.execute("FAIL ghost")

        connection = fake.created[0]
        assert connection.rollbacks == 1
        assert fake.server.durable == []
        # Rolled back rather than abandoned, so the connection is still usable.
        assert fake.discarded == []
        assert connection.get_transaction_status() is False

    async def test_failed_read_rolls_back(self) -> None:
        fake = TransactionalAiomysqlPool()
        pool = MySQLPool(pool=fake)

        with self.assertRaisesRegex(RuntimeError, "aborted part-way"):
            await pool.fetch_all("FAIL ghost")

        assert fake.created[0].rollbacks == 1
        assert fake.server.durable == []
        assert fake.discarded == []

    async def test_leaves_a_transaction_it_did_not_open_untouched(self) -> None:
        fake = PreDirtiedMysqlPool()
        pool = MySQLPool(pool=fake)

        await pool.fetch_all("SELECT x FROM t")

        connection = fake.created[0]
        assert connection.commits == 0
        assert connection.rollbacks == 0
        assert fake.server.durable == []

    async def test_autocommit_session_needs_no_transaction_control(self) -> None:
        fake = TransactionalAiomysqlPool(autocommit=True)
        pool = MySQLPool(pool=fake)

        await pool.execute("INSERT gamma")
        await pool.fetch_all("SELECT x FROM t")

        connection = fake.created[0]
        assert fake.server.durable == ["gamma"]
        assert connection.commits == 0
        assert connection.rollbacks == 0
