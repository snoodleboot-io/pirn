"""Async Neo4j connection pool backed by the :mod:`neo4j` driver."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.graph.neo4j_config import Neo4jConfig


class Neo4jPool(DatabaseConnectionPool):
    """Async Neo4j driver wrapper with credential-safe error reporting."""

    def __init__(
        self,
        config: Neo4jConfig | None = None,
        *,
        driver: Any = None,
    ) -> None:
        if config is None and driver is None:
            raise TypeError("Neo4jPool requires either config= or driver=")
        self._config = config
        self._driver = driver
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> Neo4jConfig | None:
        return self._config

    async def acquire(self) -> Any:
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        return driver.session(database=database)

    async def release(self, connection: Any) -> None:
        await connection.close()

    async def close(self) -> None:
        if self._driver is not None:
            await self._driver.close()
            self._driver = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("neo4j.close")

    async def execute(self, query: str, *args: Any) -> None:
        if len(args) > 1:
            raise ValueError(
                "Neo4jPool.execute() accepts at most one positional parameter "
                "(a dict of named parameters)."
            )
        parameters: dict[str, Any] = dict(args[0]) if args else {}
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        session = driver.session(database=database)
        try:
            await session.run(query, parameters)
        finally:
            await session.close()

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        if len(args) > 1:
            raise ValueError(
                "Neo4jPool.fetch_all() accepts at most one positional parameter "
                "(a dict of named parameters)."
            )
        parameters: dict[str, Any] = dict(args[0]) if args else {}
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        session = driver.session(database=database)
        try:
            result = await session.run(query, parameters)
            records = await result.values()
            return [dict(r) for r in records]
        finally:
            await session.close()

    async def execute_many(
        self, query: str, args_seq: Iterable[dict[str, Any]]
    ) -> None:
        for params in args_seq:
            await self.execute(query, params)

    async def _ensure_driver(self) -> Any:
        if self._closed:
            raise RuntimeError("Neo4jPool is closed")
        if self._driver is None:
            self._driver = await self._create_driver()
        return self._driver

    async def _create_driver(self) -> Any:
        try:
            import neo4j  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "Neo4jPool requires neo4j; install via pip install pirn[neo4j]"
            ) from exc
        if self._config is None:
            raise RuntimeError("Neo4jPool: missing config and no injected driver")
        try:
            driver = neo4j.AsyncGraphDatabase.driver(
                self._config.uri,
                auth=(self._config.user, self._config.password),
                max_connection_pool_size=self._config.max_connection_pool_size,
                connection_timeout=self._config.connection_timeout,
                encrypted=self._config.encrypted,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("neo4j.connect")
        return driver
