"""Async MySQL connection pool backed by :mod:`aiomysql`.

aiomysql exposes an asyncio-native pool whose connections yield cursors
that accept ``%s`` parameter markers. ``%s`` is the *standard* MySQL
placeholder — it is **not** Python string interpolation. We therefore
reject only ``{...}``-style brace interpolation; ``%s`` is allowed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.mysql_config import MySQLConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class MySQLPool(DatabaseConnectionPool):
    """Async MySQL pool with credential-safe error reporting.

    Wraps an :class:`aiomysql.Pool`. Cursor lifecycle is internal — the
    pool checks out a connection, opens a cursor, executes, then returns
    the connection to the underlying aiomysql pool.

    Parameter style: aiomysql uses ``%s`` placeholders (the canonical MySQL
    parameter marker). That is **not** considered inline interpolation —
    only ``{...}``-style brace interpolation is rejected here.

    **Transaction ownership.** ``execute``, ``execute_many`` and ``fetch_all``
    each end exactly the transaction *their own statement* opened, and never
    touch one they found already open: success commits, failure rolls back.

    The discriminator is ``aiomysql.Connection.get_transaction_status()``,
    which returns MySQL's own ``SERVER_STATUS_IN_TRANS`` flag as carried on
    the last OK/EOF packet. That makes it a true equivalent of
    ``sqlite3.Connection.in_transaction`` — the server's answer, not a
    client-side guess — so the same before/after sampling used by the SQLite
    pools transplants directly.

    Reads need this as much as writes do. aiomysql leaves ``autocommit`` at
    the driver default of ``False``, under which InnoDB opens a transaction
    for a plain ``SELECT`` and pins a read view. A ``fetch_all`` that returned
    its connection mid-transaction was not merely untidy: ``aiomysql.Pool``'s
    ``release()`` samples the same flag and *closes* a connection still in a
    transaction rather than returning it to the free list, so every read paid
    a fresh TCP connect and handshake.
    """

    _inline_interpolation_pattern = r"\{[^}]*\}"

    def __init__(
        self,
        config: MySQLConfig | None = None,
        *,
        pool: Any | None = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("MySQLPool requires either config= or pool=")
        if config is not None and not isinstance(config, MySQLConfig):
            raise TypeError(
                f"MySQLPool: config must be a MySQLConfig instance, got {type(config).__name__}"
            )
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> MySQLConfig | None:
        return self._config

    async def acquire(self) -> Any:
        pool = await self._ensure_pool()
        return await pool.acquire()

    async def release(self, connection: Any) -> None:
        pool = await self._ensure_pool()
        await pool.release(connection)

    async def close(self) -> None:
        if self._pool is not None:
            close_fn = getattr(self._pool, "close", None)
            if callable(close_fn):
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
            wait_fn = getattr(self._pool, "wait_closed", None)
            if callable(wait_fn):
                result = wait_fn()
                if hasattr(result, "__await__"):
                    await result  # type: ignore[misc]
            self._pool = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("mysql.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        params = list(parameters or ())
        connection = await pool.acquire()
        try:
            status_on_entry = self._transaction_status(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.execute(query, params)
                    rowcount = getattr(cursor, "rowcount", None)
                finally:
                    await cursor.close()
            except BaseException:
                if self._opened_transaction(connection, status_on_entry):
                    await self._end_transaction(connection, "rollback")
                raise
            if self._opened_transaction(connection, status_on_entry):
                await self._end_transaction(connection, "commit")
            return rowcount
        finally:
            await pool.release(connection)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        params = list(parameters or ())
        connection = await pool.acquire()
        try:
            status_on_entry = self._transaction_status(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                finally:
                    await cursor.close()
            except BaseException:
                if self._opened_transaction(connection, status_on_entry):
                    await self._end_transaction(connection, "rollback")
                raise
            if self._opened_transaction(connection, status_on_entry):
                await self._end_transaction(connection, "commit")
            return [tuple(r) for r in rows]
        finally:
            await pool.release(connection)

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        rows = [list(p) for p in parameter_seq]
        connection = await pool.acquire()
        try:
            status_on_entry = self._transaction_status(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.executemany(query, rows)
                    rowcount = getattr(cursor, "rowcount", None)
                finally:
                    await cursor.close()
            except BaseException:
                if self._opened_transaction(connection, status_on_entry):
                    await self._end_transaction(connection, "rollback")
                raise
            if self._opened_transaction(connection, status_on_entry):
                await self._end_transaction(connection, "commit")
            return rowcount
        finally:
            await pool.release(connection)

    @staticmethod
    def _transaction_status(connection: Any) -> bool | None:
        """MySQL's ``SERVER_STATUS_IN_TRANS`` flag for *connection*.

        Returns ``None`` when the connection does not report transaction
        status at all. Every real ``aiomysql.Connection`` does; a stand-in
        supplied through the ``pool=`` seam need not.
        """
        status_fn = getattr(connection, "get_transaction_status", None)
        if not callable(status_fn):
            return None
        return bool(status_fn())

    @classmethod
    def _opened_transaction(cls, connection: Any, status_on_entry: bool | None) -> bool:
        """Whether the statement just run is what opened the now-open transaction.

        Args:
            connection: The aiomysql-shaped connection the statement ran on.
            status_on_entry: :meth:`_transaction_status` sampled before the
                statement ran.

        Returns:
            ``True`` only when a transaction is open now and none was open
            before, which makes this call its owner — and so the one
            responsible for ending it.
        """
        status_now = cls._transaction_status(connection)
        if status_now is None:
            # Undiscriminable stand-in: treat the call as the owner. Ending a
            # transaction that was never opened is a no-op, whereas leaving one
            # open is the defect this guards.
            return True
        return status_now and not bool(status_on_entry)

    @staticmethod
    async def _end_transaction(connection: Any, verb: str) -> None:
        """Call ``connection.commit()`` or ``connection.rollback()``.

        Tolerates both sync and async driver methods, matching the rest of
        this pool's handling of the injectable ``pool=`` seam.
        """
        method = getattr(connection, verb, None)
        if not callable(method):
            return
        result = method()
        if hasattr(result, "__await__"):
            await result  # type: ignore[misc]

    async def _ensure_pool(self) -> Any:
        if self._closed:
            raise RuntimeError("MySQLPool is closed")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        try:
            import aiomysql  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MySQLPool requires aiomysql; install via `pip install pirn[mysql]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("MySQLPool: missing config and no injected pool")

        kwargs: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "user": self._config.user,
            "password": self._config.password,
            "db": self._config.database,
            "charset": self._config.charset,
            "minsize": self._config.min_size,
            "maxsize": self._config.max_size,
        }
        # aiomysql rejects ``None`` for several keys; drop empties.
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        try:
            pool = await aiomysql.create_pool(**kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("mysql.connect")
        return pool
