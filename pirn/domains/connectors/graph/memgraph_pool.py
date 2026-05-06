"""Async Memgraph connection pool backed by :mod:`gqlalchemy`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.graph.memgraph_config import MemgraphConfig


class MemgraphPool(DatabaseConnectionPool):
    """Memgraph connection wrapper with credential-safe error reporting."""

    def __init__(
        self,
        config: MemgraphConfig | None = None,
        *,
        connection: Any = None,
    ) -> None:
        if config is None and connection is None:
            raise TypeError("MemgraphPool requires either config= or connection=")
        self._config = config
        self._connection = connection
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> MemgraphConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_connection()

    async def release(self, connection: Any) -> None:
        # Connection is reused; no-op.
        pass

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("memgraph.close")

    async def execute(self, query: str, *args: Any) -> None:
        conn = await self._ensure_connection()
        parameters = args[0] if args else None
        await conn.execute(query, parameters=parameters)

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        conn = await self._ensure_connection()
        parameters = args[0] if args else None
        results = await conn.execute(query, parameters=parameters)
        return [dict(r) for r in results]

    async def execute_many(self, query: str, args_seq: Iterable[Any]) -> None:
        for params in args_seq:
            await self.execute(query, params)

    async def _ensure_connection(self) -> Any:
        if self._closed:
            raise RuntimeError("MemgraphPool is closed")
        if self._connection is None:
            self._connection = await self._create_connection()
        return self._connection

    async def _create_connection(self) -> Any:
        try:
            import gqlalchemy  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "MemgraphPool requires gqlalchemy; install via pip install pirn[memgraph]"
            ) from exc
        if self._config is None:
            raise RuntimeError("MemgraphPool: missing config and no injected connection")
        try:
            conn = gqlalchemy.Memgraph(
                host=self._config.host,
                port=self._config.port,
                username=self._config.username,
                password=self._config.password,
                encrypted=self._config.encrypted,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("memgraph.connect")
        return conn
