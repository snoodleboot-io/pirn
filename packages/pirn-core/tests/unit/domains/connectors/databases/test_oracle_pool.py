"""Unit tests for :class:`OraclePool`.

Uses an injected stub client that mirrors the cursor-based slice of the
``oracledb`` API. No real Oracle server or ``oracledb`` package needed.
"""

from __future__ import annotations

import unittest
import unittest.mock
import sys
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.oracle_config import OracleConfig
from pirn.connectors.databases.oracle_pool import OraclePool

# ──────────────────────────────────────────────────────────── fake client


class FakeOracleCursor:
    def __init__(self, parent: FakeOracleClient) -> None:
        self._parent = parent
        self._last_query: str | None = None
        self.rowcount = 0
        self.closed = False

    def execute(self, query: str, params: list[Any]) -> None:
        self._parent.executed.append((query, list(params)))
        self._last_query = query
        self.rowcount = 1

    def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._parent.executed_many.append((query, [list(r) for r in rows]))
        self.rowcount = len(rows)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._parent.responses.get(self._last_query or "", [])

    def close(self) -> None:
        self.closed = True


class FakeOracleClient:
    """Mirrors the connection / pool surface ``OraclePool`` calls into."""

    def __init__(self) -> None:
        self.executed: list[tuple[str, list[Any]]] = []
        self.executed_many: list[tuple[str, list[list[Any]]]] = []
        self.responses: dict[str, list[tuple[Any, ...]]] = {}
        self.closed = False

    def cursor(self) -> FakeOracleCursor:
        return FakeOracleCursor(self)

    def close(self) -> None:
        self.closed = True


# ──────────────────────────────────────────────── transaction-faithful double


class FakeOracleError(Exception):
    """Stands in for ``oracledb.DatabaseError``."""


class FakeOracleDatabase:
    """The durable side of the fake — rows that survived a ``COMMIT``."""

    def __init__(self) -> None:
        self.rows: list[tuple[Any, ...]] = []


class FakeTransactionalCursor:
    """Cursor over a :class:`FakeTransactionalConnection`."""

    def __init__(self, connection: FakeTransactionalConnection) -> None:
        self._connection = connection
        self.rowcount = 0
        self.closed = False

    def execute(self, statement: str, parameters: list[Any]) -> None:
        self.rowcount = self._connection.run(statement, list(parameters))

    def executemany(self, statement: str, rows: list[list[Any]]) -> None:
        # python-oracledb without ``batcherrors`` stops at the first failing
        # row and *keeps* the rows already applied, leaving the transaction
        # open — the Oracle analogue of SQLite's ``UPDATE ... OR FAIL``.
        for row in rows:
            self.rowcount += self._connection.run(statement, list(row))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._connection.fetch_last_rows()

    def close(self) -> None:
        self.closed = True


class FakeTransactionalConnection:
    """A non-autocommit ``oracledb``-shaped connection.

    Models exactly the Oracle semantics :class:`OraclePool` depends on:

    * DML stages rows and opens a transaction, which
      ``transaction_in_progress`` reports — the driver attribute that stands in
      for ``sqlite3.Connection.in_transaction``;
    * ``commit()`` makes the staged rows durable and ``rollback()`` discards
      them; both end the transaction;
    * ``close()`` discards anything uncommitted, which is what python-oracledb
      does and why a missing commit loses the write *silently*;
    * a ``SELECT`` opens no transaction and sees durable rows plus this
      transaction's own staged rows;
    * ``fetchall()`` on a statement that was not a query raises, as the real
      driver does.
    """

    def __init__(
        self,
        database: FakeOracleDatabase,
        *,
        failing_values: frozenset[Any] = frozenset(),
    ) -> None:
        self._database = database
        self._staged: list[tuple[Any, ...]] = []
        self._failing_values = failing_values
        self._last_rows: list[tuple[Any, ...]] | None = None
        self._in_transaction = False
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    @property
    def transaction_in_progress(self) -> bool:
        """Read-only, as on a real ``oracledb.Connection``."""
        return self._in_transaction

    def cursor(self) -> FakeTransactionalCursor:
        return FakeTransactionalCursor(self)

    def run(self, statement: str, parameters: list[Any]) -> int:
        verb = statement.split()[0].upper()
        if verb == "SELECT":
            self._last_rows = [*self._database.rows, *self._staged]
            return 0
        if verb == "INSERT":
            self._last_rows = None
            value = parameters[0]
            if value in self._failing_values:
                raise FakeOracleError(f"ORA-00001: unique constraint violated ({value!r})")
            self._staged.append(tuple(parameters))
            self._in_transaction = True
            return 1
        raise AssertionError(f"fake connection does not model: {statement}")

    def fetch_last_rows(self) -> list[tuple[Any, ...]]:
        if self._last_rows is None:
            raise FakeOracleError("ORA-01003: no statement parsed")
        return list(self._last_rows)

    def commit(self) -> None:
        self.commits += 1
        self._database.rows.extend(self._staged)
        self._discard()

    def rollback(self) -> None:
        self.rollbacks += 1
        self._discard()

    def close(self) -> None:
        self._discard()  # python-oracledb rolls back an open transaction on close
        self.closed = True

    def _discard(self) -> None:
        self._staged.clear()
        self._in_transaction = False


class NoFlagConnection(FakeTransactionalConnection):
    """A pre-2.3 python-oracledb shape: no ``transaction_in_progress`` at all.

    Raising ``AttributeError`` from the property is indistinguishable, to the
    ``getattr(..., None)`` probe under test, from the attribute being absent.
    """

    @property
    def transaction_in_progress(self) -> bool:
        raise AttributeError("transaction_in_progress")


class UnreadableFlagConnection(FakeTransactionalConnection):
    """Reading the flag raises, as it does once the session has dropped.

    The real property calls ``_verify_connected()`` first, so it raises a
    ``DatabaseError`` rather than an ``AttributeError`` — which ``getattr`` will
    not swallow.
    """

    @property
    def transaction_in_progress(self) -> bool:
        raise FakeOracleError("DPY-1001: not connected to database")


# ───────────────────────────────────────────────────────────── conformance


class _StandaloneTests(unittest.TestCase):
    def test_implements_database_connection_pool(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        assert isinstance(pool, DatabaseConnectionPool)

    def test_construction_requires_config_or_client(self) -> None:
        with self.assertRaisesRegex(TypeError, "config= or client="):
            OraclePool()

    def test_construction_rejects_bogus_config_type(self) -> None:
        with self.assertRaisesRegex(TypeError, "OracleConfig"):
            OraclePool(config="not-a-config")  # type: ignore[arg-type]


# ────────────────────────────────────────────────────────── delegation


class TestDelegation(unittest.IsolatedAsyncioTestCase):
    async def test_execute_passes_query_and_params(self) -> None:
        fake = FakeOracleClient()
        pool = OraclePool(client=fake)
        await pool.execute("INSERT INTO t (x, y) VALUES (:x, :y)", [1, "hello"])
        assert fake.executed == [("INSERT INTO t (x, y) VALUES (:x, :y)", [1, "hello"])]

    async def test_fetch_all_returns_rows(self) -> None:
        fake = FakeOracleClient()
        fake.responses["SELECT id FROM t WHERE x = :x"] = [(1,), (2,)]
        pool = OraclePool(client=fake)
        rows = await pool.fetch_all("SELECT id FROM t WHERE x = :x", [99])
        assert rows == [(1,), (2,)]

    async def test_execute_many_batches(self) -> None:
        fake = FakeOracleClient()
        pool = OraclePool(client=fake)
        await pool.execute_many("INSERT INTO t VALUES (:x, :y)", [(1, "a"), (2, "b")])
        assert fake.executed_many == [("INSERT INTO t VALUES (:x, :y)", [[1, "a"], [2, "b"]])]


# ────────────────────────────────────────────────────── transaction ownership


class TestTransactionOwnership(unittest.IsolatedAsyncioTestCase):
    """The pool ends exactly the transaction each call opened — no more."""

    async def test_write_is_durable_across_close_and_reopen(self) -> None:
        database = FakeOracleDatabase()
        pool = OraclePool(client=FakeTransactionalConnection(database))

        await pool.execute("INSERT INTO t (x) VALUES (:x)", ["kept"])
        await pool.close()

        reopened = OraclePool(client=FakeTransactionalConnection(database))
        assert await reopened.fetch_all("SELECT x FROM t") == [("kept",)]

    async def test_execute_many_is_durable_across_close_and_reopen(self) -> None:
        database = FakeOracleDatabase()
        pool = OraclePool(client=FakeTransactionalConnection(database))

        await pool.execute_many("INSERT INTO t (x) VALUES (:x)", [["a"], ["b"]])
        await pool.close()

        reopened = OraclePool(client=FakeTransactionalConnection(database))
        assert await reopened.fetch_all("SELECT x FROM t") == [("a",), ("b",)]

    async def test_failed_write_leaves_no_residue(self) -> None:
        database = FakeOracleDatabase()
        connection = FakeTransactionalConnection(database, failing_values=frozenset({"boom"}))
        pool = OraclePool(client=connection)

        with self.assertRaises(FakeOracleError):
            await pool.execute("INSERT INTO t (x) VALUES (:x)", ["boom"])

        assert connection.commits == 0
        assert connection.transaction_in_progress is False
        assert database.rows == []

    async def test_partially_applied_batch_is_rolled_back(self) -> None:
        database = FakeOracleDatabase()
        connection = FakeTransactionalConnection(database, failing_values=frozenset({"boom"}))
        pool = OraclePool(client=connection)

        with self.assertRaises(FakeOracleError):
            await pool.execute_many("INSERT INTO t (x) VALUES (:x)", [["ok"], ["boom"]])

        assert connection.rollbacks == 1
        assert connection.commits == 0
        assert connection.transaction_in_progress is False
        assert database.rows == []

    async def test_read_issues_no_commit(self) -> None:
        database = FakeOracleDatabase()
        database.rows.append(("durable",))
        connection = FakeTransactionalConnection(database)
        pool = OraclePool(client=connection)

        assert await pool.fetch_all("SELECT x FROM t") == [("durable",)]
        assert connection.commits == 0
        assert connection.rollbacks == 0

    async def test_read_leaves_a_caller_transaction_open(self) -> None:
        database = FakeOracleDatabase()
        connection = FakeTransactionalConnection(database)
        caller_cursor = connection.cursor()
        caller_cursor.execute("INSERT INTO t (x) VALUES (:x)", ["callers"])
        pool = OraclePool(client=connection)

        assert await pool.fetch_all("SELECT x FROM t") == [("callers",)]
        assert connection.commits == 0
        assert connection.rollbacks == 0
        assert connection.transaction_in_progress is True

    async def test_write_does_not_adopt_a_caller_transaction(self) -> None:
        database = FakeOracleDatabase()
        connection = FakeTransactionalConnection(database)
        caller_cursor = connection.cursor()
        caller_cursor.execute("INSERT INTO t (x) VALUES (:x)", ["callers"])
        pool = OraclePool(client=connection)

        await pool.execute("INSERT INTO t (x) VALUES (:x)", ["pools"])

        assert connection.commits == 0
        assert connection.transaction_in_progress is True
        assert database.rows == []

    async def test_dml_reaching_the_read_path_is_not_stranded(self) -> None:
        database = FakeOracleDatabase()
        connection = FakeTransactionalConnection(database)
        pool = OraclePool(client=connection)

        with self.assertRaises(FakeOracleError):
            await pool.fetch_all("INSERT INTO t (x) VALUES (:x)", ["stranded"])

        assert connection.rollbacks == 1
        assert connection.transaction_in_progress is False
        assert database.rows == []


class TestUnreportableTransactionState(unittest.IsolatedAsyncioTestCase):
    """A client that cannot report ``transaction_in_progress`` still stays safe."""

    async def test_write_commits_when_the_flag_is_absent(self) -> None:
        database = FakeOracleDatabase()
        connection = NoFlagConnection(database)
        pool = OraclePool(client=connection)

        await pool.execute("INSERT INTO t (x) VALUES (:x)", ["kept"])

        assert connection.commits == 1
        assert database.rows == [("kept",)]

    async def test_write_commits_when_reading_the_flag_raises(self) -> None:
        database = FakeOracleDatabase()
        connection = UnreadableFlagConnection(database)
        pool = OraclePool(client=connection)

        await pool.execute("INSERT INTO t (x) VALUES (:x)", ["kept"])

        assert connection.commits == 1
        assert database.rows == [("kept",)]

    async def test_read_still_commits_nothing_when_the_flag_is_absent(self) -> None:
        database = FakeOracleDatabase()
        database.rows.append(("durable",))
        connection = NoFlagConnection(database)
        pool = OraclePool(client=connection)

        assert await pool.fetch_all("SELECT x FROM t") == [("durable",)]
        assert connection.commits == 0
        assert connection.rollbacks == 0

    async def test_statement_error_is_not_masked_by_an_unreadable_flag(self) -> None:
        database = FakeOracleDatabase()
        connection = UnreadableFlagConnection(database, failing_values=frozenset({"boom"}))
        pool = OraclePool(client=connection)

        # The statement's own ORA error surfaces, not the flag's InterfaceError.
        with self.assertRaisesRegex(FakeOracleError, "ORA-00001"):
            await pool.execute("INSERT INTO t (x) VALUES (:x)", ["boom"])


# ─────────────────────────────────────────────────────────── query safety


class TestQuerySafety(unittest.TestCase):
    def test_rejects_fstring_placeholder(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = {v}")

    def test_rejects_percent_s_placeholder(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            pool._reject_inline_interpolation("SELECT * FROM t WHERE x = %s")

    def test_accepts_named_bind(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        pool._reject_inline_interpolation("SELECT * FROM t WHERE x = :x")


class TestQuerySafetyEnforced(unittest.IsolatedAsyncioTestCase):
    async def test_execute_rejects_format_query(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.execute("SELECT %s FROM t", [1])

    async def test_fetch_all_rejects_format_query(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        with self.assertRaisesRegex(ValueError, "interpolation"):
            await pool.fetch_all("SELECT * FROM t WHERE x = {evil}")


# ─────────────────────────────────────────────────────────────── lifecycle


class TestLifecycle(unittest.IsolatedAsyncioTestCase):
    async def test_close_closes_underlying_client(self) -> None:
        fake = FakeOracleClient()
        pool = OraclePool(client=fake)
        await pool.close()
        assert fake.closed is True

    async def test_close_is_idempotent(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        await pool.close()
        await pool.close()

    async def test_acquire_after_close_raises(self) -> None:
        pool = OraclePool(client=FakeOracleClient())
        await pool.close()
        with self.assertRaisesRegex(RuntimeError, "closed"):
            await pool.acquire()


# ────────────────────────────────────────────────────────── credential safety


class TestCredentialSafety(unittest.TestCase):
    def test_repr_redacts_password(self) -> None:
        cfg = OracleConfig(
            user="alice",
            password="hunter2-leaks",
            dsn="db.example.com:1521/orclpdb",
        )
        text = repr(cfg)
        assert "hunter2-leaks" not in text
        assert "<redacted>" in text

    def test_audit_dict_redacts_password(self) -> None:
        cfg = OracleConfig(
            user="alice",
            password="hunter2-leaks",
            dsn="db.example.com:1521/orclpdb",
        )
        d = cfg.to_audit_dict()
        assert d["password"] == "<redacted>"
        assert d["user"] == "alice"
        assert d["dsn"] == "db.example.com:1521/orclpdb"

    def test_password_listed_in_sensitive_fields(self) -> None:
        assert "password" in OracleConfig.sensitive_fields


# ────────────────────────────────────────────── config-built client (PIR-824)


class TestConfigBuiltClient(unittest.IsolatedAsyncioTestCase):
    """The ``config=`` seam must produce a client statements can actually use.

    This path built an ``oracledb.ConnectionPool``, which exposes
    acquire/release/close/drop and **no** ``cursor()`` — so every statement
    method raised ``AttributeError`` the moment it ran. It never ran: no test
    constructed ``OraclePool(config=...)`` and drove a statement, which is
    exactly how a broken public path stayed broken. That end-to-end exercise is
    what this class adds.
    """

    @staticmethod
    def _oracledb_double(database: FakeOracleDatabase) -> Any:
        """Return a stand-in ``oracledb`` module recording how it was called."""

        class _FakePool:
            """What `create_pool` returns: no `cursor`, which is the defect."""

            def acquire(self) -> Any:  # pragma: no cover - must never be used
                raise AssertionError("create_pool path should not be taken")

        class _Module:
            def __init__(self) -> None:
                self.connect_calls: list[dict[str, Any]] = []
                self.create_pool_calls: list[dict[str, Any]] = []

            def connect(self, **kwargs: Any) -> Any:
                self.connect_calls.append(kwargs)
                return FakeTransactionalConnection(database)

            def create_pool(self, **kwargs: Any) -> Any:
                self.create_pool_calls.append(kwargs)
                return _FakePool()

        return _Module()

    async def test_a_statement_runs_end_to_end_from_a_config(self) -> None:
        # The exercise that did not exist. Against the old implementation this
        # fails with AttributeError: '_FakePool' object has no attribute 'cursor'.
        database = FakeOracleDatabase()
        module = self._oracledb_double(database)
        pool = OraclePool(config=OracleConfig(user="alice", password="pw", dsn="host:1521/ORCL"))

        with unittest.mock.patch.dict(sys.modules, {"oracledb": module}):
            rowcount = await pool.execute("INSERT INTO t VALUES (:1)", ["a"])
            rows = await pool.fetch_all("SELECT * FROM t")

        assert rowcount == 1
        assert rows == [("a",)]

    async def test_it_connects_rather_than_creating_a_pool(self) -> None:
        database = FakeOracleDatabase()
        module = self._oracledb_double(database)
        pool = OraclePool(config=OracleConfig(user="alice", dsn="host:1521/ORCL"))

        with unittest.mock.patch.dict(sys.modules, {"oracledb": module}):
            await pool.execute("INSERT INTO t VALUES (:1)", ["a"])

        assert module.create_pool_calls == []
        assert len(module.connect_calls) == 1

    async def test_only_the_configured_fields_are_forwarded(self) -> None:
        # No pool bounds are sent — the config no longer has any, and passing
        # min/max to `connect` would be a TypeError.
        database = FakeOracleDatabase()
        module = self._oracledb_double(database)
        pool = OraclePool(config=OracleConfig(user="alice", dsn="host:1521/ORCL"))

        with unittest.mock.patch.dict(sys.modules, {"oracledb": module}):
            await pool.execute("INSERT INTO t VALUES (:1)", ["a"])

        assert module.connect_calls[0] == {"user": "alice", "dsn": "host:1521/ORCL"}

    async def test_the_config_client_commits_like_the_injected_one(self) -> None:
        # PIR-821's transaction ownership must hold on this seam too, not just
        # on `client=` — the whole reason a single connection is kept.
        database = FakeOracleDatabase()
        module = self._oracledb_double(database)
        pool = OraclePool(config=OracleConfig(user="alice", dsn="host:1521/ORCL"))

        with unittest.mock.patch.dict(sys.modules, {"oracledb": module}):
            await pool.execute("INSERT INTO t VALUES (:1)", ["durable"])

        assert database.rows == [("durable",)]
