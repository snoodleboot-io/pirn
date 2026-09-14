"""``DatabaseConnectionPool.transaction()`` on the in-process SQL pools (PIR-873).

Each test runs a real engine: a scope that raises must leave no statement it
issued behind, a clean scope must commit all of them, and statements outside the
scope must not be swept into it.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.database_transaction import DatabaseTransaction
from pirn.exceptions.connector_closed_error import ConnectorClosedError

pytest.importorskip("aiosqlite")
pytest.importorskip("duckdb")

from pirn.connectors.databases.duckdb_config import DuckdbConfig
from pirn.connectors.databases.duckdb_pool import DuckdbPool
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_pool import SqlitePool


class _Boom(Exception):
    pass


class TestBaseInterface:
    def test_transaction_raises_not_implemented(self) -> None:
        with pytest.raises(NotImplementedError, match="must implement transaction"):
            DatabaseConnectionPool().transaction()


class _PoolTransactionContract:
    """Behaviour every in-process pool's transaction must show."""

    async def _pool(self, tmp: Path) -> DatabaseConnectionPool:
        raise NotImplementedError

    async def test_exception_rolls_back_every_statement(self, tmp_path: Path) -> None:
        pool = await self._pool(tmp_path)
        try:
            await pool.execute("CREATE TABLE t (id INTEGER, v VARCHAR)")
            await pool.execute("INSERT INTO t VALUES (?, ?)", (1, "old"))
            with pytest.raises(_Boom):
                async with pool.transaction() as tx:
                    await tx.execute("UPDATE t SET v = ? WHERE id = ?", ("expired", 1))
                    await tx.execute_many("INSERT INTO t VALUES (?, ?)", [(2, "a"), (3, "b")])
                    raise _Boom
            assert await pool.fetch_all("SELECT id, v FROM t ORDER BY id") == [(1, "old")]
        finally:
            await pool.close()

    async def test_clean_exit_commits_every_statement(self, tmp_path: Path) -> None:
        pool = await self._pool(tmp_path)
        try:
            await pool.execute("CREATE TABLE t (id INTEGER, v VARCHAR)")
            async with pool.transaction() as tx:
                await tx.execute("INSERT INTO t VALUES (?, ?)", (1, "a"))
                await tx.execute_many("INSERT INTO t VALUES (?, ?)", [(2, "b")])
                assert await tx.fetch_all("SELECT COUNT(*) FROM t") == [(2,)]
            assert await pool.fetch_all("SELECT id, v FROM t ORDER BY id") == [(1, "a"), (2, "b")]
        finally:
            await pool.close()

    async def test_handle_is_unusable_after_the_scope(self, tmp_path: Path) -> None:
        pool = await self._pool(tmp_path)
        try:
            async with pool.transaction() as tx:
                assert isinstance(tx, DatabaseTransaction)
            with pytest.raises(ConnectorClosedError):
                await tx.fetch_all("SELECT 1")
            with pytest.raises(RuntimeError):
                await tx.close()
            with pytest.raises(RuntimeError):
                tx.transaction()
        finally:
            await pool.close()

    async def test_handle_keeps_the_interpolation_guard(self, tmp_path: Path) -> None:
        pool = await self._pool(tmp_path)
        try:
            async with pool.transaction() as tx:
                with pytest.raises(ValueError, match="interpolation"):
                    await tx.execute("SELECT {x}")
        finally:
            await pool.close()


class TestSqlitePoolTransaction(_PoolTransactionContract):
    async def _pool(self, tmp: Path) -> DatabaseConnectionPool:
        return SqlitePool(SqliteConfig(database=str(tmp / "t.db")))

    async def test_concurrent_pool_statement_does_not_join_the_scope(self, tmp_path: Path) -> None:
        # One shared connection: before the lock, a statement another task issued
        # on the pool while the scope was open ran inside it and was rolled back.
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "t.db")))
        try:
            await pool.execute("CREATE TABLE t (id INTEGER)")
            entered = asyncio.Event()
            task = asyncio.create_task(self._insert_once_entered(pool, entered))
            with pytest.raises(_Boom):
                async with pool.transaction() as tx:
                    await tx.execute("INSERT INTO t VALUES (?)", (1,))
                    entered.set()
                    await asyncio.sleep(0.05)
                    raise _Boom
            await task
            assert await pool.fetch_all("SELECT id FROM t") == [(99,)]
        finally:
            await pool.close()

    @staticmethod
    async def _insert_once_entered(pool: DatabaseConnectionPool, entered: asyncio.Event) -> None:
        await entered.wait()
        await pool.execute("INSERT INTO t VALUES (?)", (99,))

    async def test_pool_statement_inside_own_scope_raises(self, tmp_path: Path) -> None:
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "t.db")))
        try:
            async with pool.transaction():
                with pytest.raises(RuntimeError, match="use the handle"):
                    await pool.fetch_all("SELECT 1")
        finally:
            await pool.close()

    async def test_refuses_to_adopt_a_caller_transaction(self, tmp_path: Path) -> None:
        pool = SqlitePool(SqliteConfig(database=str(tmp_path / "t.db")))
        try:
            await pool.execute("CREATE TABLE t (id INTEGER)")
            connection = await pool.acquire()
            await connection.execute("BEGIN")  # a caller-owned transaction, begun by hand
            with pytest.raises(RuntimeError, match="already open"):
                async with pool.transaction():
                    pass
        finally:
            await pool.close()


class TestDuckdbPoolTransaction(_PoolTransactionContract):
    async def _pool(self, tmp: Path) -> DatabaseConnectionPool:
        return DuckdbPool(DuckdbConfig(database=str(tmp / "t.duckdb")))

    async def test_in_memory_database_is_shared_with_the_scope(self) -> None:
        pool = DuckdbPool(DuckdbConfig(database=":memory:"))
        try:
            await pool.execute("CREATE TABLE t (id INTEGER)")
            async with pool.transaction() as tx:
                await tx.execute("INSERT INTO t VALUES (?)", (1,))
            assert await pool.fetch_all("SELECT id FROM t") == [(1,)]
        finally:
            await pool.close()

    async def test_execute_many_on_the_pool(self, tmp_path: Path) -> None:
        pool = DuckdbPool(DuckdbConfig(database=str(tmp_path / "t.duckdb")))
        try:
            await pool.execute("CREATE TABLE t (id INTEGER)")
            await pool.execute_many("INSERT INTO t VALUES (?)", [(1,), (2,)])
            assert await pool.fetch_all("SELECT id FROM t ORDER BY id") == [(1,), (2,)]
        finally:
            await pool.close()
