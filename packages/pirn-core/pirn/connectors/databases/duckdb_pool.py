"""Async wrapper around DuckDB.

DuckDB is in-process and synchronous; we wrap calls in
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on long queries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.duckdb_config import DuckdbConfig
from pirn.core.optional_dependency import OptionalDependency


class DuckdbPool(DatabaseConnectionPool):
    """Single-connection DuckDB pool."""

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
        self._reject_inline_interpolation(query)
        connection = await self.acquire()
        params = list(parameters or ())
        return await asyncio.to_thread(connection.execute, query, params)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self._reject_inline_interpolation(query)
        connection = await self.acquire()
        params = list(parameters or ())
        return await asyncio.to_thread(self._sync_fetch_all, connection, query, params)

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
