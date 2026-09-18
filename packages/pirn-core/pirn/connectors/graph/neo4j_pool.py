"""Async Neo4j connection pool backed by the :mod:`neo4j` driver."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.graph.neo4j_config import Neo4jConfig
from pirn.connectors.neo4j_transaction import Neo4jTransaction
from pirn.core.optional_dependency import OptionalDependency


class Neo4jPool(DatabaseConnectionPool):
    """Async Neo4j driver wrapper with credential-safe error reporting."""

    # Cypher binds parameters as ``$name`` and writes map literals as ``{k: v}``,
    # so the base pattern's brace rule would reject valid Cypher — e.g.
    # ``CREATE (n:N {id: $id})``. Only printf-style markers are interpolation here.
    _inline_interpolation_pattern = r"%[sd]"

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

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> None:
        bound: dict[str, Any] = dict(parameters) if parameters is not None else {}
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        session = driver.session(database=database)
        try:
            await session.run(query, bound)
        finally:
            await session.close()

    async def fetch_all(
        self, query: str, parameters: Iterable[Any] | None = None
    ) -> list[dict[str, Any]]:
        bound: dict[str, Any] = dict(parameters) if parameters is not None else {}
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        session = driver.session(database=database)
        try:
            result = await session.run(query, bound)
            records = await result.values()
            return [dict(r) for r in records]
        finally:
            await session.close()

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        for params in parameter_seq:
            await self.execute(query, params)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[DatabaseConnectionPool]:
        """Run the block's Cypher as one explicit Neo4j transaction.

        Opens a session, begins an explicit transaction on it and yields a
        :class:`Neo4jTransaction` bound to that transaction. A clean exit commits;
        an exception rolls back and propagates. The session closes either way.

        The pool's own methods open a session per statement and so run each in its
        own implicit transaction; statements issued on the pool while this scope is
        open are therefore *not* part of it, as the interface's contract says.
        """
        driver = await self._ensure_driver()
        database = self._config.database if self._config else None
        session = driver.session(database=database)
        try:
            neo4j_transaction = await session.begin_transaction()
            handle = Neo4jTransaction(neo4j_transaction, self)
            try:
                try:
                    yield handle
                except BaseException:
                    await neo4j_transaction.rollback()
                    raise
                await neo4j_transaction.commit()
            finally:
                handle.finish()
        finally:
            await session.close()

    async def _ensure_driver(self) -> Any:
        if self._closed:
            raise self._closed_error("Neo4jPool")
        if self._driver is None:
            self._driver = await self._create_driver()
        return self._driver

    async def _create_driver(self) -> Any:
        neo4j = OptionalDependency.require("neo4j", extra="neo4j")
        if self._config is None:
            raise self._missing_config_error("Neo4jPool", "driver")
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
