"""Async MSSQL connection pool backed by :mod:`aioodbc`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.mssql_config import MssqlConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class MssqlPool(DatabaseConnectionPool):
    """Async MSSQL pool with credential-safe error reporting.

    Wraps an :class:`aioodbc.Pool`. Cursor lifecycle is internal — the
    pool checks out a connection, opens a cursor for the call, then
    returns the connection to the underlying aioodbc pool.

    **Transaction ownership.** ``execute``, ``execute_many`` and ``fetch_all``
    each end exactly the transaction *their own statement* opened: success
    commits, failure rolls back. Nothing else is committed on their behalf.

    Establishing that ownership takes an extra step here, because pyodbc —
    and so aioodbc — exposes no equivalent of
    ``sqlite3.Connection.in_transaction`` or of aiomysql's
    ``get_transaction_status()``. There is no flag to sample, so ownership
    cannot be *inferred* after the fact; it has to be made structural
    instead, by guaranteeing the connection is transaction-free on checkout.
    :meth:`release` is what provides that guarantee — see its docstring.

    The one signal ODBC does offer is ``autocommit``. With it set there is
    never an open transaction to own and the pool issues no transaction
    control at all; with it clear ODBC opens a transaction implicitly at the
    first statement after connect/commit/rollback — a ``SELECT`` included —
    and this pool ends the one it opened.
    """

    def __init__(
        self,
        config: MssqlConfig | None = None,
        *,
        pool: Any = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("MssqlPool requires either config= or pool=")
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> MssqlConfig | None:
        return self._config

    async def acquire(self) -> Any:
        pool = await self._ensure_pool()
        return await pool.acquire()

    async def release(self, connection: Any) -> None:
        """Return *connection* to the pool, discarding work left uncommitted.

        aioodbc's own ``Pool.release`` appends the connection straight back
        onto the free list — it neither rolls back nor inspects transaction
        state, unlike ``aiomysql.Pool.release``, which destroys a connection
        still in a transaction. So without this rollback, DML a caller left
        uncommitted survived into the next checkout and was committed by
        whatever statement ran next, on someone else's behalf.

        Discarding it is the DBAPI contract for a connection handed back
        without an explicit commit, and it is what lets the query methods
        above treat a checked-out connection as transaction-free, and so
        treat any transaction open when they finish as their own.
        """
        pool = await self._ensure_pool()
        try:
            if self._manages_transactions(connection):
                await self._end_transaction(connection, "rollback")
        finally:
            # A rollback that fails (dead connection, say) must not cost the
            # caller the checkout as well — release regardless.
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
        self._logger.debug("mssql.close")

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
            owns_transaction = self._manages_transactions(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.execute(query, params)
                    rowcount = getattr(cursor, "rowcount", None)
                finally:
                    await cursor.close()
            except BaseException:
                if owns_transaction:
                    await self._end_transaction(connection, "rollback")
                raise
            if owns_transaction:
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
            owns_transaction = self._manages_transactions(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.execute(query, params)
                    rows = await cursor.fetchall()
                finally:
                    await cursor.close()
            except BaseException:
                if owns_transaction:
                    await self._end_transaction(connection, "rollback")
                raise
            if owns_transaction:
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
            owns_transaction = self._manages_transactions(connection)
            try:
                cursor = await connection.cursor()
                try:
                    await cursor.executemany(query, rows)
                    rowcount = getattr(cursor, "rowcount", None)
                finally:
                    await cursor.close()
            except BaseException:
                if owns_transaction:
                    await self._end_transaction(connection, "rollback")
                raise
            if owns_transaction:
                await self._end_transaction(connection, "commit")
            return rowcount
        finally:
            await pool.release(connection)

    @staticmethod
    def _manages_transactions(connection: Any) -> bool:
        """Whether this pool has to end transactions on *connection* itself.

        ``autocommit`` is the only transaction-related state pyodbc exposes —
        there is no in-transaction flag to sample — so it is the whole of the
        discriminator. Clear means ODBC opens a transaction implicitly and
        someone must end it; set means each statement commits itself and there
        is nothing to own.

        A stand-in that does not expose ``autocommit`` at all is read as
        ``autocommit=False``, the conservative direction: an unnecessary
        ``COMMIT``/``ROLLBACK`` is a no-op under ODBC autocommit, whereas a
        skipped one leaves the transaction this guard exists to close.
        """
        return not bool(getattr(connection, "autocommit", False))

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
            raise RuntimeError("MssqlPool is closed")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        try:
            import aioodbc  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "MssqlPool requires aioodbc; install via `pip install pirn[mssql]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("MssqlPool: missing config and no injected pool")

        kwargs: dict[str, Any] = {
            "dsn": self._config.build_dsn(),
            "minsize": self._config.min_size,
            "maxsize": self._config.max_size,
            "autocommit": self._config.autocommit,
        }
        try:
            pool = await aioodbc.create_pool(**kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("mssql.connect")
        return pool
