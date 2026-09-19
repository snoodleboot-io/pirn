"""Connection pool wrapper around the synchronous Snowflake connector.

``snowflake-connector-python`` is synchronous; calls run in a worker
thread via :func:`asyncio.to_thread` so the connector cooperates with
pirn's async runtime without blocking the event loop on long queries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.snowflake_config import SnowflakeConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.threaded_cursor_transaction import ThreadedCursorTransaction
from pirn.core.optional_dependency import OptionalDependency


class SnowflakePool(DatabaseConnectionPool):
    """Single-connection Snowflake pool.

    The Snowflake driver maintains its own session-level connection state
    (warehouse / database / schema / role) so a single underlying
    connection is sufficient. ``acquire`` returns the shared connection
    and ``release`` is a no-op.

    **Transactions.** This pool issues no transaction control of its own and
    relies on the driver's session default, ``AUTOCOMMIT=TRUE``, under which
    each statement commits itself. That is correct for a connection this pool
    opens from ``config``, which never turns autocommit off.

    It is *not* guaranteed for a connection supplied through ``client=``. A
    caller injecting one built with ``autocommit=False`` gets a session in
    which Snowflake opens a transaction implicitly and nothing here ever
    commits it, so writes made through :meth:`execute` are discarded when the
    connection closes — silently, with no error. Inject an autocommit
    connection, or drive ``BEGIN``/``COMMIT`` on it yourself.
    """

    def __init__(
        self,
        config: SnowflakeConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("SnowflakePool requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)
        self._transaction_lock = asyncio.Lock()
        self._transaction_task: asyncio.Task[Any] | None = None

    @property
    def config(self) -> SnowflakeConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_client()

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("snowflake.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            client = await self._ensure_client()
            params = list(parameters or ())
            return await asyncio.to_thread(self._sync_execute, client, query, params)

    @staticmethod
    def _sync_execute(client: Any, query: str, params: list[Any]) -> Any:
        cursor = client.cursor()
        try:
            cursor.execute(query, params)
            return cursor.rowcount
        finally:
            cursor.close()

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            client = await self._ensure_client()
            params = list(parameters or ())
            return await asyncio.to_thread(self._sync_fetch_all, client, query, params)

    @staticmethod
    def _sync_fetch_all(client: Any, query: str, params: list[Any]) -> list[tuple[Any, ...]]:
        cursor = client.cursor()
        try:
            cursor.execute(query, params)
            return [tuple(r) for r in cursor.fetchall()]
        finally:
            cursor.close()

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        self.reject_inline_interpolation(query)
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            client = await self._ensure_client()
            rows = [list(p) for p in parameter_seq]
            return await asyncio.to_thread(self._sync_execute_many, client, query, rows)

    @staticmethod
    def _sync_execute_many(client: Any, query: str, rows: list[Any]) -> Any:
        cursor = client.cursor()
        try:
            cursor.executemany(query, rows)
            return cursor.rowcount
        finally:
            cursor.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[DatabaseConnectionPool]:
        """Run the block's statements as one Snowflake transaction.

        Issues ``BEGIN`` on the pool's client and yields a
        :class:`ThreadedCursorTransaction` on it. A clean exit commits; an
        exception rolls back and propagates.

        The pool holds one client, so a statement issued through the pool by
        another task while the scope is open would silently join — and be
        committed or rolled back with — this transaction. The scope therefore
        holds a lock for its whole duration and the statement methods wait for
        it; a statement issued on the pool from *inside* the scope's own task is
        refused rather than deadlocked.
        """
        self._reject_statement_inside_own_transaction()
        async with self._transaction_lock:
            client = await self._ensure_client()
            self._transaction_task = asyncio.current_task()
            handle = ThreadedCursorTransaction(client, self)
            try:
                await asyncio.to_thread(self._sync_execute, client, "BEGIN", [])
                try:
                    yield handle
                except BaseException:
                    await asyncio.to_thread(self._sync_execute, client, "ROLLBACK", [])
                    raise
                await asyncio.to_thread(self._sync_execute, client, "COMMIT", [])
            finally:
                handle.finish()
                self._transaction_task = None

    def _reject_statement_inside_own_transaction(self) -> None:
        """Raise when the task holding this pool's transaction scope uses the pool directly.

        Waiting for the lock there would deadlock: the scope cannot end until the
        statement returns. The statement belongs on the yielded handle.
        """
        task = self._transaction_task
        if task is not None and task is asyncio.current_task():
            raise RuntimeError(
                "SnowflakePool: statement issued on the pool inside its own "
                "transaction scope; use the handle `async with pool.transaction()` yielded"
            )

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise self._closed_error("SnowflakePool")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        snowflake_connector = OptionalDependency.require("snowflake.connector", extra="snowflake")
        if self._config is None:
            raise self._missing_config_error("SnowflakePool", "client")

        kwargs: dict[str, Any] = {}
        for name in (
            "account",
            "user",
            "password",
            "warehouse",
            "database",
            "schema",
            "role",
        ):
            value = getattr(self._config, name)
            if value is not None:
                kwargs[name] = value
        try:
            client: Any = await asyncio.to_thread(snowflake_connector.connect, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("snowflake.connect")
        return client
