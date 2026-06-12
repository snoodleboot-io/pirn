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
            cursor = await connection.cursor()
            try:
                await cursor.execute(query, params)
                rowcount = getattr(cursor, "rowcount", None)
                commit_fn = getattr(connection, "commit", None)
                if callable(commit_fn):
                    result = commit_fn()
                    if hasattr(result, "__await__"):
                        await result  # type: ignore[misc]
                return rowcount
            finally:
                await cursor.close()
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
            cursor = await connection.cursor()
            try:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()
                return [tuple(r) for r in rows]
            finally:
                await cursor.close()
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
            cursor = await connection.cursor()
            try:
                await cursor.executemany(query, rows)
                rowcount = getattr(cursor, "rowcount", None)
                commit_fn = getattr(connection, "commit", None)
                if callable(commit_fn):
                    result = commit_fn()
                    if hasattr(result, "__await__"):
                        await result  # type: ignore[misc]
                return rowcount
            finally:
                await cursor.close()
        finally:
            await pool.release(connection)

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
