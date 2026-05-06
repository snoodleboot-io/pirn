"""Async MSSQL connection pool backed by :mod:`aioodbc`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.mssql_config import MssqlConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class MssqlPool(DatabaseConnectionPool):
    """Async MSSQL pool with credential-safe error reporting.

    Wraps an :class:`aioodbc.Pool`. Cursor lifecycle is internal — the
    pool checks out a connection, opens a cursor for the call, then
    returns the connection to the underlying aioodbc pool.
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
        pool = await self._ensure_pool()
        await pool.release(connection)

    async def close(self) -> None:
        if self._pool is not None:
            close_fn = getattr(self._pool, "close", None)
            if callable(close_fn):
                result = close_fn()
                if hasattr(result, "__await__"):
                    await result
            wait_fn = getattr(self._pool, "wait_closed", None)
            if callable(wait_fn):
                result = wait_fn()
                if hasattr(result, "__await__"):
                    await result
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
            cursor = await connection.cursor()
            try:
                await cursor.execute(query, params)
                rowcount = getattr(cursor, "rowcount", None)
                commit_fn = getattr(connection, "commit", None)
                if callable(commit_fn):
                    result = commit_fn()
                    if hasattr(result, "__await__"):
                        await result
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
                        await result
                return rowcount
            finally:
                await cursor.close()
        finally:
            await pool.release(connection)

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
