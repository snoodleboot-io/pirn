"""Async TimescaleDB connection pool backed by :mod:`asyncpg`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.timeseries.timescaledb_config import TimescaleDBConfig


class TimescaleDBPool(DatabaseConnectionPool):
    """Async TimescaleDB pool; TimescaleDB is a PostgreSQL extension."""

    def __init__(
        self,
        config: TimescaleDBConfig | None = None,
        *,
        pool: Any = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("TimescaleDBPool requires either config= or pool=")
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> TimescaleDBConfig | None:
        return self._config

    @property
    def schema(self) -> str | None:
        return self._config.schema if self._config is not None else None

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
        self._logger.debug("timescaledb.close")

    async def execute(self, query: str, *args: Any) -> str:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        return await pool.execute(query, *args)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        rows = await pool.fetch(query, *args)
        return list(rows)

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        await pool.executemany(query, [tuple(a) for a in args_seq])

    async def _ensure_pool(self) -> Any:
        if self._closed:
            raise RuntimeError("TimescaleDBPool is closed")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        try:
            import asyncpg
        except ImportError as exc:
            raise ImportError(
                "TimescaleDBPool requires asyncpg; install via `pip install pirn[timescaledb]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("TimescaleDBPool: missing config and no injected pool")

        kwargs: dict[str, Any] = {
            "min_size": self._config.min_size,
            "max_size": self._config.max_size,
            "command_timeout": self._config.command_timeout,
        }
        if self._config.schema != "public":
            kwargs["server_settings"] = {"search_path": self._config.schema}

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
            self._reraise_scrubbed(exc)
        self._logger.debug("timescaledb.connect")
        return pool
