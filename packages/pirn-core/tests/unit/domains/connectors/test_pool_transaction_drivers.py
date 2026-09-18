"""``transaction()`` on the pools that drive a remote engine (PIR-873).

``test_pool_transaction.py`` covers the two in-process engines. The other pools
drive a server nothing in CI can reach, so each is driven here through a stand-in
supplied at the pool's own ``pool=`` / ``client=`` / ``driver=`` seam — the seam
the pools already expose for exactly this.

The stand-ins are **not** mocks of the methods under test: each wraps a real
``sqlite3`` connection and maps the driver shape onto it, so ``COMMIT`` and
``ROLLBACK`` are a real engine's, and the rollback assertions fail if the scope
does not actually roll back. What each test exercises is the pool's real
``transaction()``, the real transaction handle class, and the real
commit-or-rollback dispatch; only the wire protocol is stood in for.

Every test here fails on the pre-PIR-873 tree: ``transaction()`` was implemented
for SQLite and DuckDB only, so these pools raised
``NotImplementedError("<Pool> must implement transaction()")``.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from pirn.connectors.asyncpg_transaction import AsyncpgTransaction
from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.mssql_pool import MssqlPool
from pirn.connectors.databases.mysql_pool import MySQLPool
from pirn.connectors.databases.oracle_pool import OraclePool
from pirn.connectors.databases.postgres_pool import PostgresPool
from pirn.connectors.databases.redshift_pool import RedshiftPool
from pirn.connectors.databases.snowflake_pool import SnowflakePool
from pirn.connectors.dbapi_cursor_transaction import DbapiCursorTransaction
from pirn.connectors.mongodb_transaction import MongodbTransaction
from pirn.connectors.neo4j_transaction import Neo4jTransaction
from pirn.connectors.threaded_cursor_transaction import ThreadedCursorTransaction
from pirn.connectors.timeseries.timescaledb_pool import TimescaleDBPool


class _Boom(Exception):
    pass


def _sqlite() -> sqlite3.Connection:
    """A real in-memory SQLite connection with implicit transactions turned off."""
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.isolation_level = None  # we issue BEGIN/COMMIT/ROLLBACK ourselves
    connection.execute("CREATE TABLE t (id INTEGER, v TEXT)")
    connection.execute("INSERT INTO t VALUES (1, 'old')")
    return connection


class _AsyncpgTransactionHandle:
    """asyncpg's ``Connection.transaction()`` object, over real SQLite."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    async def start(self) -> None:
        self._raw.execute("BEGIN")

    async def commit(self) -> None:
        self._raw.execute("COMMIT")

    async def rollback(self) -> None:
        self._raw.execute("ROLLBACK")


class _AsyncpgConnection:
    """asyncpg's ``Connection``: variadic binds, ``fetch``, ``transaction()``."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._raw = raw

    def transaction(self) -> _AsyncpgTransactionHandle:
        return _AsyncpgTransactionHandle(self._raw)

    async def execute(self, query: str, *args: Any) -> str:
        self._raw.execute(query, args)
        return "OK"

    async def fetch(self, query: str, *args: Any) -> list[tuple[Any, ...]]:
        return [tuple(r) for r in self._raw.execute(query, args).fetchall()]

    async def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        self._raw.executemany(query, rows)


class _AsyncpgPool:
    """asyncpg's ``Pool``: one connection, acquire/release, pool-level statements."""

    def __init__(self) -> None:
        self.raw = _sqlite()
        self._connection = _AsyncpgConnection(self.raw)

    async def acquire(self) -> _AsyncpgConnection:
        return self._connection

    async def release(self, connection: _AsyncpgConnection) -> None:
        return None

    async def close(self) -> None:
        self.raw.close()

    async def execute(self, query: str, *args: Any) -> str:
        return await self._connection.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[tuple[Any, ...]]:
        return await self._connection.fetch(query, *args)

    async def executemany(self, query: str, rows: list[tuple[Any, ...]]) -> None:
        await self._connection.executemany(query, rows)


class _DbapiCursor:
    """An async DB-API cursor over a real SQLite cursor."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._cursor = raw.cursor()
        self.rowcount = -1

    async def execute(self, query: str, params: list[Any]) -> None:
        self._cursor.execute(query, params)
        self.rowcount = self._cursor.rowcount

    async def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._cursor.executemany(query, rows)
        self.rowcount = self._cursor.rowcount

    async def fetchall(self) -> list[tuple[Any, ...]]:
        return [tuple(r) for r in self._cursor.fetchall()]

    async def close(self) -> None:
        self._cursor.close()


class _DbapiConnection:
    """An async DB-API connection over real SQLite: cursor/begin/commit/rollback."""

    def __init__(self, raw: sqlite3.Connection, *, autocommit: bool = False) -> None:
        self._raw = raw
        self.autocommit = autocommit
        self._in_transaction = False

    async def cursor(self) -> _DbapiCursor:
        return _DbapiCursor(self._raw)

    async def begin(self) -> None:
        self._raw.execute("BEGIN")
        self._in_transaction = True

    async def commit(self) -> None:
        if self._in_transaction:
            self._raw.execute("COMMIT")
            self._in_transaction = False

    async def rollback(self) -> None:
        if self._in_transaction:
            self._raw.execute("ROLLBACK")
            self._in_transaction = False

    def get_transaction_status(self) -> bool:
        return self._in_transaction


class _DbapiPool:
    """An aiomysql/aioodbc-shaped pool: one connection, acquire/release."""

    def __init__(self, *, autocommit: bool = False) -> None:
        self.raw = _sqlite()
        self._connection = _DbapiConnection(self.raw, autocommit=autocommit)

    async def acquire(self) -> _DbapiConnection:
        return self._connection

    async def release(self, connection: _DbapiConnection) -> None:
        return None

    def close(self) -> None:
        self.raw.close()


class _SyncCursor:
    """A synchronous DB-API cursor over a real SQLite cursor."""

    def __init__(self, raw: sqlite3.Connection) -> None:
        self._cursor = raw.cursor()
        self.rowcount = -1

    def execute(self, query: str, params: list[Any]) -> None:
        self._cursor.execute(query, params)
        self.rowcount = self._cursor.rowcount

    def executemany(self, query: str, rows: list[list[Any]]) -> None:
        self._cursor.executemany(query, rows)
        self.rowcount = self._cursor.rowcount

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [tuple(r) for r in self._cursor.fetchall()]

    def close(self) -> None:
        self._cursor.close()


class _SyncClient:
    """An oracledb/snowflake-shaped synchronous client over real SQLite."""

    def __init__(self) -> None:
        self.raw = _sqlite()
        self.transaction_in_progress = False

    def cursor(self) -> _SyncCursor:
        return _SyncCursor(self.raw)

    def commit(self) -> None:
        if self.transaction_in_progress:
            self.raw.execute("COMMIT")
            self.transaction_in_progress = False

    def rollback(self) -> None:
        if self.transaction_in_progress:
            self.raw.execute("ROLLBACK")
            self.transaction_in_progress = False

    def close(self) -> None:
        self.raw.close()


class _OracleClient(_SyncClient):
    """Oracle opens its transaction implicitly on the first DML statement."""

    def cursor(self) -> _SyncCursor:
        self.transaction_in_progress = True
        self.raw.execute("SAVEPOINT oracle_implicit")
        return _SyncCursor(self.raw)

    def commit(self) -> None:
        if self.transaction_in_progress:
            self.raw.execute("RELEASE SAVEPOINT oracle_implicit")
            self.transaction_in_progress = False

    def rollback(self) -> None:
        if self.transaction_in_progress:
            self.raw.execute("ROLLBACK TO SAVEPOINT oracle_implicit")
            self.transaction_in_progress = False


def _rows(raw: sqlite3.Connection) -> list[tuple[Any, ...]]:
    return [tuple(r) for r in raw.execute("SELECT id, v FROM t ORDER BY id").fetchall()]


class TestAsyncpgBackedPools:
    """Postgres, Redshift and TimescaleDB share one asyncpg-shaped transaction."""

    @pytest.mark.parametrize(
        "pool_class", [PostgresPool, RedshiftPool, TimescaleDBPool], ids=lambda c: c.__name__
    )
    async def test_exception_rolls_back_every_statement(self, pool_class: Any) -> None:
        driver = _AsyncpgPool()
        pool = pool_class(pool=driver)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                assert isinstance(tx, AsyncpgTransaction)
                await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                await tx.execute_many("INSERT INTO t VALUES (?, ?)", [(2, "a"), (3, "b")])
                assert len(await tx.fetch_all("SELECT id FROM t")) == 3
                raise _Boom
        assert _rows(driver.raw) == [(1, "old")]

    @pytest.mark.parametrize(
        "pool_class", [PostgresPool, RedshiftPool, TimescaleDBPool], ids=lambda c: c.__name__
    )
    async def test_clean_exit_commits_every_statement(self, pool_class: Any) -> None:
        driver = _AsyncpgPool()
        pool = pool_class(pool=driver)
        async with pool.transaction() as tx:
            await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("new", 1))
            await tx.execute_many("INSERT INTO t VALUES (?, ?)", [(2, "a")])
        assert _rows(driver.raw) == [(1, "new"), (2, "a")]

    async def test_handle_is_unusable_after_the_scope(self) -> None:
        pool = PostgresPool(pool=_AsyncpgPool())
        async with pool.transaction() as tx:
            pass
        with pytest.raises(Exception, match="closed"):
            await tx.fetch_all("SELECT 1")


class TestMySQLPoolTransaction:
    async def test_exception_rolls_back_every_statement(self) -> None:
        driver = _DbapiPool()
        pool = MySQLPool(pool=driver)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                assert isinstance(tx, DbapiCursorTransaction)
                await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                await tx.execute_many("INSERT INTO t VALUES (?, ?)", [(2, "a")])
                raise _Boom
        assert _rows(driver.raw) == [(1, "old")]

    async def test_clean_exit_commits_every_statement(self) -> None:
        driver = _DbapiPool()
        pool = MySQLPool(pool=driver)
        async with pool.transaction() as tx:
            await tx.execute("INSERT INTO t VALUES (?, ?)", (2, "a"))
            assert await tx.fetch_all("SELECT id FROM t ORDER BY id") == [(1,), (2,)]
        assert _rows(driver.raw) == [(1, "old"), (2, "a")]

    async def test_connection_that_cannot_begin_is_refused(self) -> None:
        """A stand-in without ``begin()`` gets a refusal, not a silently flat scope."""
        driver = _DbapiPool()
        connection = await driver.acquire()
        connection.begin = None  # a driver seam that exposes no begin()
        pool = MySQLPool(pool=driver)
        with pytest.raises(RuntimeError, match="cannot begin a transaction"):
            async with pool.transaction():
                pass
        assert _rows(driver.raw) == [(1, "old")]


class TestMssqlPoolTransaction:
    async def test_exception_rolls_back_every_statement(self) -> None:
        driver = _DbapiPool()
        # ODBC opens the transaction implicitly; mirror that in the stand-in.
        connection = await driver.acquire()
        await connection.begin()
        pool = MssqlPool(pool=driver)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                raise _Boom
        assert _rows(driver.raw) == [(1, "old")]

    async def test_clean_exit_commits_every_statement(self) -> None:
        driver = _DbapiPool()
        connection = await driver.acquire()
        await connection.begin()
        pool = MssqlPool(pool=driver)
        async with pool.transaction() as tx:
            await tx.execute("INSERT INTO t VALUES (?, ?)", (2, "a"))
        assert _rows(driver.raw) == [(1, "old"), (2, "a")]

    async def test_autocommit_connection_is_refused(self) -> None:
        pool = MssqlPool(pool=_DbapiPool(autocommit=True))
        with pytest.raises(RuntimeError, match="autocommit"):
            async with pool.transaction():
                pass


class TestOraclePoolTransaction:
    async def test_exception_rolls_back_every_statement(self) -> None:
        client = _OracleClient()
        pool = OraclePool(client=client)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                assert isinstance(tx, ThreadedCursorTransaction)
                await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                raise _Boom
        assert _rows(client.raw) == [(1, "old")]

    async def test_clean_exit_commits_every_statement(self) -> None:
        client = _OracleClient()
        pool = OraclePool(client=client)
        async with pool.transaction() as tx:
            await tx.execute("INSERT INTO t VALUES (?, ?)", (2, "a"))
        assert _rows(client.raw) == [(1, "old"), (2, "a")]

    async def test_pool_statement_inside_own_scope_raises(self) -> None:
        pool = OraclePool(client=_OracleClient())
        async with pool.transaction():
            with pytest.raises(RuntimeError, match="use the handle"):
                await pool.fetch_all("SELECT 1")

    async def test_refuses_to_adopt_a_caller_transaction(self) -> None:
        client = _OracleClient()
        client.transaction_in_progress = True
        pool = OraclePool(client=client)
        with pytest.raises(RuntimeError, match="already open"):
            async with pool.transaction():
                pass


class TestSnowflakePoolTransaction:
    async def test_exception_rolls_back_every_statement(self) -> None:
        client = _SyncClient()
        client.transaction_in_progress = True  # BEGIN through the pool arms commit/rollback
        pool = SnowflakePool(client=client)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                raise _Boom
        assert _rows(client.raw) == [(1, "old")]

    async def test_clean_exit_commits_every_statement(self) -> None:
        client = _SyncClient()
        client.transaction_in_progress = True
        pool = SnowflakePool(client=client)
        async with pool.transaction() as tx:
            await tx.execute("INSERT INTO t VALUES (?, ?)", (2, "a"))
        assert _rows(client.raw) == [(1, "old"), (2, "a")]

    async def test_pool_statement_inside_own_scope_raises(self) -> None:
        client = _SyncClient()
        client.transaction_in_progress = True
        pool = SnowflakePool(client=client)
        async with pool.transaction():
            with pytest.raises(RuntimeError, match="use the handle"):
                await pool.fetch_all("SELECT id FROM t")


class _Neo4jResult:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    async def values(self) -> list[dict[str, Any]]:
        return self._rows


class _Neo4jTransactionHandle:
    """neo4j's ``AsyncTransaction``: run/commit/rollback, recorded and replayed."""

    def __init__(self, store: list[str]) -> None:
        self._store = store
        self._staged: list[str] = []
        self.ended = ""

    async def run(self, query: str, parameters: dict[str, Any]) -> _Neo4jResult:
        self._staged.append(query)
        return _Neo4jResult([dict(parameters)])

    async def commit(self) -> None:
        self._store.extend(self._staged)
        self._staged.clear()
        self.ended = "commit"

    async def rollback(self) -> None:
        self._staged.clear()
        self.ended = "rollback"


class _Neo4jSession:
    def __init__(self, store: list[str]) -> None:
        self._store = store
        self.transaction: _Neo4jTransactionHandle | None = None
        self.closed = False

    async def begin_transaction(self) -> _Neo4jTransactionHandle:
        self.transaction = _Neo4jTransactionHandle(self._store)
        return self.transaction

    async def close(self) -> None:
        self.closed = True


class _Neo4jDriver:
    def __init__(self) -> None:
        self.store: list[str] = []
        self.sessions: list[_Neo4jSession] = []

    def session(self, database: str | None = None) -> _Neo4jSession:
        session = _Neo4jSession(self.store)
        self.sessions.append(session)
        return session


class TestNeo4jPoolTransaction:
    async def test_exception_rolls_back_and_closes_the_session(self) -> None:
        from pirn.connectors.graph.neo4j_pool import Neo4jPool

        driver = _Neo4jDriver()
        pool = Neo4jPool(driver=driver)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                assert isinstance(tx, Neo4jTransaction)
                await tx.execute("CREATE (n:N {id: $id})", {"id": 1})
                raise _Boom
        assert driver.store == []
        assert driver.sessions[0].transaction is not None
        assert driver.sessions[0].transaction.ended == "rollback"
        assert driver.sessions[0].closed

    async def test_clean_exit_commits_every_statement(self) -> None:
        from pirn.connectors.graph.neo4j_pool import Neo4jPool

        driver = _Neo4jDriver()
        pool = Neo4jPool(driver=driver)
        async with pool.transaction() as tx:
            await tx.execute("CREATE (n:N {id: $id})", {"id": 1})
            await tx.execute_many("CREATE (n:N {id: $id})", [{"id": 2}, {"id": 3}])
        assert len(driver.store) == 3
        assert driver.sessions[0].closed


class _MongoCollection:
    def __init__(self, committed: list[dict[str, Any]], staged: list[dict[str, Any]]) -> None:
        self._committed = committed
        self._staged = staged

    async def insert_one(self, document: Any, session: Any = None) -> Any:
        if session is None:
            raise AssertionError("insert_one issued outside the transaction's session")
        self._staged.append(dict(document))
        return type("_R", (), {"inserted_id": len(self._staged)})()

    async def insert_many(self, documents: list[Any], session: Any = None) -> None:
        if session is None:
            raise AssertionError("insert_many issued outside the transaction's session")
        self._staged.extend(dict(d) for d in documents)

    def find(self, filter_document: Any, session: Any = None) -> Any:
        rows = [*self._committed, *self._staged]

        class _Cursor:
            @staticmethod
            async def to_list(length: int | None) -> list[dict[str, Any]]:
                return rows

        return _Cursor()


class _MongoDatabase:
    def __init__(self) -> None:
        self.committed: list[dict[str, Any]] = []
        self.staged: list[dict[str, Any]] = []

    def __getitem__(self, name: str) -> _MongoCollection:
        return _MongoCollection(self.committed, self.staged)


class _MongoSession:
    def __init__(self, database: _MongoDatabase) -> None:
        self._database = database
        self.started = False
        self.ended = False

    def start_transaction(self) -> None:
        self.started = True

    async def commit_transaction(self) -> None:
        self._database.committed.extend(self._database.staged)
        self._database.staged.clear()

    async def abort_transaction(self) -> None:
        self._database.staged.clear()

    async def end_session(self) -> None:
        self.ended = True


class _MongoClient:
    def __init__(self) -> None:
        self.database = _MongoDatabase()
        self.session: _MongoSession | None = None

    def __getitem__(self, name: str) -> _MongoDatabase:
        return self.database

    async def start_session(self) -> _MongoSession:
        self.session = _MongoSession(self.database)
        return self.session

    def close(self) -> None:
        return None


class TestMongoDBPoolTransaction:
    def _pool(self, client: _MongoClient) -> DatabaseConnectionPool:
        from pirn.connectors.document.mongodb_config import MongoDBConfig
        from pirn.connectors.document.mongodb_pool import MongoDBPool

        pool = MongoDBPool(MongoDBConfig(database="db"), client=client)
        return pool

    async def test_exception_aborts_every_write(self) -> None:
        client = _MongoClient()
        pool = self._pool(client)
        with pytest.raises(_Boom):
            async with pool.transaction() as tx:
                assert isinstance(tx, MongodbTransaction)
                await tx.execute("people", {"name": "alice"})
                await tx.execute_many("people", [{"name": "bob"}])
                raise _Boom
        assert client.database.committed == []
        assert client.database.staged == []
        assert client.session is not None
        assert client.session.ended

    async def test_clean_exit_commits_every_write(self) -> None:
        client = _MongoClient()
        pool = self._pool(client)
        async with pool.transaction() as tx:
            await tx.execute("people", {"name": "alice"})
            assert await tx.fetch_all("people") == [{"name": "alice"}]
        assert client.database.committed == [{"name": "alice"}]
        assert client.session is not None
        assert client.session.ended
