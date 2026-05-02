"""Async Redshift connection pool backed by :mod:`asyncpg`.

Redshift is wire-compatible with PostgreSQL so we reuse asyncpg. Mirrors
:class:`pirn.domains.connectors.databases.postgres_pool.PostgresPool`'s
surface — Redshift just disables the prepared-statement cache by default
because it does not support server-side prepared statements.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.redshift_config import RedshiftConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class RedshiftPool(DatabaseConnectionPool):
    """Async Redshift pool with credential-safe error reporting."""

    def __init__(
        self,
        config: RedshiftConfig | None = None,
        *,
        pool: Any = None,
    ) -> None:
        if config is None and pool is None:
            raise TypeError("RedshiftPool requires either config= or pool=")
        self._config = config
        self._pool = pool
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> RedshiftConfig | None:
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
        self._logger.debug("redshift.close")

    async def execute(self, query: str, *args: Any) -> str:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        return await pool.execute(query, *args)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        rows = await pool.fetch(query, *args)
        return list(rows)

    async def execute_many(
        self, query: str, args_seq: Iterable[Iterable[Any]]
    ) -> None:
        self._reject_inline_interpolation(query)
        pool = await self._ensure_pool()
        await pool.executemany(query, [tuple(a) for a in args_seq])

    async def _ensure_pool(self) -> Any:
        if self._closed:
            raise RuntimeError("RedshiftPool is closed")
        if self._pool is None:
            self._pool = await self._create_pool()
        return self._pool

    async def _create_pool(self) -> Any:
        try:
            import asyncpg
        except ImportError as exc:
            raise ImportError(
                "RedshiftPool requires asyncpg; install via "
                "`pip install pirn[redshift]`"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "RedshiftPool: missing config and no injected pool"
            )

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
            self._reraise_scrubbed(exc)
        self._logger.debug("redshift.connect")
        return pool
