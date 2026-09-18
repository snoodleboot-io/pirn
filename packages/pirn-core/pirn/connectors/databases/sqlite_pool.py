"""Async SQLite connection pool.

Single connection under the hood — SQLite serialises writes, so multiple
connections do not parallelise. The pool surface is implemented for parity
with :class:`pirn.connectors.database_connection_pool.DatabaseConnectionPool`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.sqlite_config import SqliteConfig
from pirn.connectors.databases.sqlite_transaction import SqliteTransaction
from pirn.core.optional_dependency import OptionalDependency


class SqlitePool(DatabaseConnectionPool):
    """Async SQLite pool. One underlying connection.

    **Transaction ownership.** Every statement method here commits — or rolls
    back — exactly the transaction *its own statement* opened, and never touches
    one it found already open. This is the guarantee
    :meth:`~pirn_agents.connectors.column_aware_sqlite_pool.ColumnAwareSqlitePool.fetch_columns`
    (PIR-801), ``AiosqliteConnector``/``SqliteConnector`` (PIR-807) and
    ``SQLExecutor`` (PIR-817) already make; ``sqlite3`` starts an implicit
    transaction for DML only, so comparing ``in_transaction`` before and after
    the statement identifies the owner precisely:

    * a write that succeeds is committed, so it is durable once the call
      returns. Previously ``fetch_all`` neither committed nor rolled back, so a
      DML statement run through it stranded its transaction on the shared
      connection (PIR-819);
    * a statement that raises is rolled back. ``UPDATE ... OR FAIL`` aborts
      mid-statement while *keeping* the rows it already changed and leaves the
      transaction open, so without the rollback that partial write survived to
      be committed by whatever ran next — including a pure read;
    * a read, and DDL, open no transaction and so neither commit nor roll back.
      A read therefore issues no ``COMMIT``, which matters beyond tidiness:
      under ``journal_mode=DELETE`` a ``COMMIT`` must take the exclusive lock,
      so a concurrent reader would make a query that only read rows fail with
      ``database is locked``.

    Because the connection is shared, sampling the flag on entry is what
    separates this pool's own transaction from a caller's. ``execute`` and
    ``execute_many`` previously committed unconditionally, which adopted both a
    transaction stranded by an earlier ``fetch_all`` and one the caller had
    opened themselves. A caller driving this pool directly can therefore hold a
    multi-statement transaction across these calls and remains the only one who
    may end it.

    **Atomic units of work.** :meth:`transaction` issues ``BEGIN`` on the shared
    connection and yields a :class:`SqliteTransaction` whose statements all run
    inside it. Because there is only one connection, a statement issued through
    the pool by anyone else while the scope is open would silently join — and
    be committed or rolled back with — that transaction. So every statement
    method here waits for an open transaction scope to end first, and one issued
    on the pool from inside its own scope (instead of on the handle) raises
    rather than deadlocking.
    """

    def __init__(self, config: SqliteConfig) -> None:
        self._config = config
        self._connection: Any = None
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)
        self._transaction_lock = asyncio.Lock()
        self._transaction_task: asyncio.Task[Any] | None = None

    @property
    def config(self) -> SqliteConfig:
        return self._config

    async def acquire(self) -> Any:
        if self._closed:
            raise self._closed_error("SqlitePool")
        if self._connection is None:
            self._connection = await self._open_connection()
        return self._connection

    async def release(self, connection: Any) -> None:
        return None  # single-connection pool

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("sqlite.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        """Run a parameterised statement and return the cursor.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.
        """
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            return await self._execute_unlocked(query, parameters)

    async def _execute_unlocked(self, query: str, parameters: Iterable[Any] | None) -> Any:
        connection = await self.acquire()
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            cursor = await connection.execute(query, tuple(parameters or ()))
        except BaseException:
            if self._opened_transaction(connection, in_transaction_on_entry):
                await connection.rollback()
            raise
        if self._opened_transaction(connection, in_transaction_on_entry):
            await connection.commit()
        return cursor

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        """Run a parameterised statement against a sequence of parameter tuples.

        Commits only the transaction this statement opened — see the class
        docstring for why that is not an unconditional commit.
        """
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            return await self._execute_many_unlocked(query, parameter_seq)

    async def _execute_many_unlocked(
        self, query: str, parameter_seq: Iterable[Iterable[Any]]
    ) -> Any:
        connection = await self.acquire()
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            cursor = await connection.executemany(query, [tuple(p) for p in parameter_seq])
        except BaseException:
            if self._opened_transaction(connection, in_transaction_on_entry):
                await connection.rollback()
            raise
        if self._opened_transaction(connection, in_transaction_on_entry):
            await connection.commit()
        return cursor

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised SELECT and return all rows as tuples.

        A read opens no transaction and so issues no ``COMMIT``. A DML statement
        reaching here is committed rather than left stranded on the shared
        connection — see the class docstring.
        """
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            return await self._fetch_all_unlocked(query, parameters)

    async def _fetch_all_unlocked(
        self, query: str, parameters: Iterable[Any] | None
    ) -> list[tuple[Any, ...]]:
        connection = await self.acquire()
        in_transaction_on_entry = bool(connection.in_transaction)
        try:
            cursor = await connection.execute(query, tuple(parameters or ()))
            try:
                rows = await cursor.fetchall()
            finally:
                await cursor.close()
        except BaseException:
            if self._opened_transaction(connection, in_transaction_on_entry):
                await connection.rollback()
            raise
        if self._opened_transaction(connection, in_transaction_on_entry):
            await connection.commit()
        return [tuple(r) for r in rows]

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[DatabaseConnectionPool]:
        """Run the block's statements as one SQLite transaction.

        Waits for any other open scope on this pool, issues ``BEGIN`` and yields
        a :class:`SqliteTransaction` on the shared connection. A clean exit
        commits; an exception rolls back and propagates.

        Raises:
            RuntimeError: If a transaction is already open on the connection —
                one a caller began by hand is theirs to end, not this scope's.
        """
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            connection = await self.acquire()
            if connection.in_transaction:
                raise RuntimeError(
                    "SqlitePool: a transaction is already open on the connection; "
                    "end it before opening a transaction scope"
                )
            self._transaction_task = asyncio.current_task()
            handle = SqliteTransaction(connection, self)
            try:
                await connection.execute("BEGIN")
                try:
                    yield handle
                except BaseException:
                    await connection.rollback()
                    raise
                await connection.commit()
            finally:
                handle.finish()
                self._transaction_task = None

    def _reject_statement_inside_own_transaction(self) -> None:
        """Raise when the task holding this pool's transaction scope uses the pool directly.

        Waiting for the lock there would deadlock: the scope cannot end until
        the statement returns. The statement belongs on the yielded handle.
        """
        task = self._transaction_task
        if task is not None and task is asyncio.current_task():
            raise RuntimeError(
                "SqlitePool: statement issued on the pool inside its own "
                "transaction scope; use the handle `async with pool.transaction()` yielded"
            )

    @staticmethod
    def _opened_transaction(connection: Any, in_transaction_on_entry: bool) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The aiosqlite-shaped connection the statement ran on.
            in_transaction_on_entry: ``connection.in_transaction`` sampled before
                the statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one responsible
            for ending it.
        """
        return bool(connection.in_transaction) and not in_transaction_on_entry

    async def _open_connection(self) -> Any:
        aiosqlite = OptionalDependency.require("aiosqlite", extra="sqlite")

        connection = await aiosqlite.connect(
            str(self._config.database), timeout=self._config.timeout
        )
        if str(self._config.database) != ":memory:":
            await connection.execute(f"PRAGMA journal_mode={self._config.journal_mode}")
        for name, value in self._config.pragmas:
            await connection.execute(f"PRAGMA {name}={value}")
        await connection.commit()
        self._logger.debug("sqlite.connect")
        return connection
