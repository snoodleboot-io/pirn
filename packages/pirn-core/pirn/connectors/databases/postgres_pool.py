"""Async Postgres connection pool backed by :mod:`asyncpg`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.postgres_config import PostgresConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class PostgresPool(DatabaseConnectionPool):
    """Async Postgres pool with credential-safe error reporting."""

    def __init__(
        self,
        config: PostgresConfig | None = None,
        *,
        pool: Any = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("PostgresPool requires either config= or pool=")
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> PostgresConfig | None:
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
        self._logger.debug("postgres.close")

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Run a parameterised statement and return the driver status string.

        asyncpg binds values variadically, so the interface's single
        *parameters* iterable is splatted here (PIR-833). Before that this pool
        took ``*args`` directly, which meant a caller written against
        :class:`DatabaseConnectionPool` — or against any of the nine pools that
        take one iterable — passed a tuple that asyncpg then read as a single
        bind value.
        """
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        return await pool.execute(query, *tuple(parameters or ()))

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Run a parameterised read and return all rows.

        *parameters* is splatted for asyncpg; see :meth:`execute`.
        """
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        rows = await pool.fetch(query, *tuple(parameters or ()))
        return list(rows)

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        await pool.executemany(query, [tuple(p) for p in parameter_seq])

    async def _ensure_pool(self) -> Any:
        if self._closed:
            raise RuntimeError("PostgresPool is closed")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        try:
            import asyncpg
        except ImportError as exc:
            raise ImportError(
                "PostgresPool requires asyncpg; install via `pip install pirn[postgres]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("PostgresPool: missing config and no injected pool")

        kwargs: dict[str, Any] = {
            "min_size": self._config.min_size,
            "max_size": self._config.max_size,
            "command_timeout": self._config.command_timeout,
            "statement_cache_size": self._config.statement_cache_size,
        }
        try:
            if self._config.dsn:
                pool = await asyncpg.create_pool(self._config.dsn, **kwargs)
            else:
                pool = await asyncpg.create_pool(
                    host=self._config.host,
                    port=self._config.port,
                    user=self._config.user,
                    password=self._config.password,
                    database=self._config.database,
                    **kwargs,
                )
        except Exception as exc:
            # asyncpg occasionally echoes credentials in error messages —
            # scrub before letting the exception propagate.
            self._reraise_scrubbed(exc)
        self._logger.debug("postgres.connect")
        return pool
