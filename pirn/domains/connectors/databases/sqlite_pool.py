"""Async SQLite connection pool.

Single connection under the hood — SQLite serialises writes, so multiple
connections do not parallelise. The pool surface is implemented for parity
with :class:`pirn.domains.connectors.database_connection_pool.DatabaseConnectionPool`.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.sqlite_config import SqliteConfig


class SqlitePool(DatabaseConnectionPool):
    """Async SQLite pool. One underlying connection."""

    def __init__(self, config: SqliteConfig) -> None:
        self._config = config
        self._connection: Any = None
        self._closed = False
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> SqliteConfig:
        return self._config

    async def acquire(self) -> Any:
        if self._closed:
            raise RuntimeError("SqlitePool is closed")
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
        """Run a parameterised statement and commit. Returns the cursor."""
        self._reject_inline_interpolation(query)
        connection = await self.acquire()
        cursor = await connection.execute(query, tuple(parameters or ()))
        await connection.commit()
        return cursor

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        """Run a parameterised statement against a sequence of parameter tuples."""
        self._reject_inline_interpolation(query)
        connection = await self.acquire()
        cursor = await connection.executemany(query, [tuple(p) for p in parameter_seq])
        await connection.commit()
        return cursor

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        """Run a parameterised SELECT and return all rows as tuples."""
        self._reject_inline_interpolation(query)
        connection = await self.acquire()
        cursor = await connection.execute(query, tuple(parameters or ()))
        try:
            rows = await cursor.fetchall()
            return [tuple(r) for r in rows]
        finally:
            await cursor.close()

    async def _open_connection(self) -> Any:
        try:
            import aiosqlite
        except ImportError as exc:
            raise ImportError(
                "SqlitePool requires aiosqlite; install via `pip install pirn[sqlite]`"
            ) from exc

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
