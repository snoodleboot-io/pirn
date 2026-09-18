"""Async QuestDB connection pool backed by :mod:`asyncpg` (PostgreSQL wire protocol)."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.timeseries.questdb_config import QuestDBConfig
from pirn.core.optional_dependency import OptionalDependency


class QuestDBPool(DatabaseConnectionPool):
    """Async QuestDB pool using the PostgreSQL wire protocol via asyncpg."""

    def __init__(
        self,
        config: QuestDBConfig | None = None,
        *,
        pool: Any = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("QuestDBPool requires either config= or pool=")
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> QuestDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        pool = await self._ensure_pool()
        return await pool.acquire()

    async def release(self, connection: Any) -> None:
        pool = await self._ensure_pool()
        await pool.release(connection)

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("questdb.close")

    def transaction(self) -> AbstractAsyncContextManager[DatabaseConnectionPool]:
        """Refuse an atomic scope: QuestDB has none through this surface.

        QuestDB speaks the Postgres wire protocol but does not implement rollback: a
        BEGIN/COMMIT pair is accepted and then ignored, so a scope would look atomic and
        not be.

        Raises:
            NotImplementedError: Always. Issue the statements individually and
                make each one idempotent.
        """
        self._no_transaction_support("QuestDB", "its Postgres wire protocol")

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        self.reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        return await pool.execute(query, *tuple(parameters or ()))

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        self.reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        rows = await pool.fetch(query, *tuple(parameters or ()))
        return list(rows)

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        self.reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        await pool.executemany(query, [tuple(a) for a in parameter_seq])

    async def _ensure_pool(self) -> Any:
        if self._closed:
            raise self._closed_error("QuestDBPool")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        asyncpg = OptionalDependency.require("asyncpg", extra="postgres")
        if self._config is None:
            raise self._missing_config_error("QuestDBPool", "pool")
        try:
            pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.pg_port,
                user=self._config.username,
                password=self._config.password,
                database=self._config.database,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("questdb.connect")
        return pool
