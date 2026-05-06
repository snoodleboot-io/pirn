"""Async OrientDB connection pool backed by :mod:`pyorient` (sync, thread-wrapped)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.graph.orientdb_config import OrientDBConfig


class OrientDBPool(DatabaseConnectionPool):
    """OrientDB client wrapper with credential-safe error reporting.

    ``pyorient`` is synchronous; all blocking calls are dispatched through
    :func:`asyncio.to_thread` so callers get a consistent async interface.
    """

    def __init__(
        self,
        config: OrientDBConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("OrientDBPool requires either config= or client=")
        if config is not None and not client and not config.database:
            raise ValueError(
                "OrientDBPool: config.database must be non-empty when connecting"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OrientDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_client()

    async def release(self, connection: Any) -> None:
        # Client is reused; no-op.
        pass

    async def close(self) -> None:
        if self._client is not None:
            await asyncio.to_thread(self._client.db_close)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("orientdb.close")

    async def execute(self, query: str, *args: Any) -> str:
        client = await self._ensure_client()
        result = await asyncio.to_thread(client.command, query)
        return str(result)

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        results = await asyncio.to_thread(client.query, query, -1)
        return [r.oRecordData for r in results]

    async def execute_many(
        self, query: str, args_seq: Iterable[Any]
    ) -> None:
        for _ in args_seq:
            await self.execute(query)

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("OrientDBPool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import pyorient  # type: ignore[import]
        except ImportError as exc:
            raise ImportError(
                "OrientDBPool requires pyorient; install via "
                "pip install pirn[orientdb]"
            ) from exc
        if self._config is None:
            raise RuntimeError(
                "OrientDBPool: missing config and no injected client"
            )
        try:
            client = await asyncio.to_thread(
                pyorient.OrientDB, self._config.host, self._config.port
            )
            await asyncio.to_thread(
                client.connect, self._config.user, self._config.password
            )
            await asyncio.to_thread(
                client.db_open,
                self._config.database,
                self._config.user,
                self._config.password,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("orientdb.connect")
        return client
