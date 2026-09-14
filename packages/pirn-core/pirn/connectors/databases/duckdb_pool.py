"""Async wrapper around DuckDB.

DuckDB is in-process and synchronous; we wrap calls in
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on long queries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.duckdb_config import DuckdbConfig
from pirn.connectors.databases.duckdb_transaction import DuckdbTransaction
from pirn.core.optional_dependency import OptionalDependency


class DuckdbPool(DatabaseConnectionPool):
    """Single-connection DuckDB pool.

    Each statement method runs in DuckDB's autocommit mode. :meth:`transaction`
    opens a dedicated cursor — a second connection to the same database, with
    its own transaction — so statements issued on the pool while a scope is open
    stay outside it, and DuckDB's MVCC arbitrates conflicts between the two.
    """

    def __init__(self, config: DuckdbConfig) -> None:
        self._config = config
        self._connection: Any = None
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DuckdbConfig:
        return self._config

    async def acquire(self) -> Any:
        if self._closed:
            raise self._closed_error("DuckdbPool")
        if self._connection is None:
            self._connection = await self._open_connection()
        return self._connection

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        if self._connection is not None:
            await asyncio.to_thread(self._connection.close)
            self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("duckdb.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        self.reject_inline_interpolation(query)
        connection = await self.acquire()
        params = list(parameters or ())
        return await asyncio.to_thread(connection.execute, query, params)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self.reject_inline_interpolation(query)
        connection = await self.acquire()
        params = list(parameters or ())
        return await asyncio.to_thread(self._sync_fetch_all, connection, query, params)

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> Any:
        self.reject_inline_interpolation(query)
        connection = await self.acquire()
        rows = [list(p) for p in parameter_seq]
        return await asyncio.to_thread(connection.executemany, query, rows)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[DatabaseConnectionPool]:
        """Run the block's statements as one DuckDB transaction.

        Opens a cursor connection on the pool's database, ``begin()``s on it and
        yields a :class:`DuckdbTransaction`. A clean exit commits; an exception
        rolls back and propagates. The cursor is closed either way.
        """
        connection = await self.acquire()
        cursor = await asyncio.to_thread(connection.cursor)
        handle = DuckdbTransaction(cursor, self)
        try:
            await asyncio.to_thread(cursor.begin)
            try:
                yield handle
            except BaseException:
                await asyncio.to_thread(cursor.rollback)
                raise
            await asyncio.to_thread(cursor.commit)
        finally:
            handle.finish()
            await asyncio.to_thread(cursor.close)

    @staticmethod
    def _sync_fetch_all(connection: Any, query: str, params: list[Any]) -> list[tuple[Any, ...]]:
        cursor = connection.execute(query, params)
        return [tuple(r) for r in cursor.fetchall()]

    async def _open_connection(self) -> Any:
        duckdb = OptionalDependency.require("duckdb", extra="duckdb")
        connection = await asyncio.to_thread(
            duckdb.connect,
            database=str(self._config.database),
            read_only=self._config.read_only,
            config=dict(self._config.config),
        )
        self._logger.debug("duckdb.connect")
        return connection
