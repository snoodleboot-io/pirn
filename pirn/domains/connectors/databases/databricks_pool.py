"""Connection pool wrapper around the synchronous Databricks SQL connector.

``databricks-sql-connector`` is synchronous; calls run in a worker
thread via :func:`asyncio.to_thread` so the connector cooperates with
pirn's async runtime without blocking the event loop on long queries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.databases.databricks_config import DatabricksConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class DatabricksPool(DatabaseConnectionPool):
    """Single-connection Databricks SQL pool.

    The driver maintains its own session/cluster routing so a single
    underlying connection is sufficient. ``acquire`` returns the shared
    connection and ``release`` is a no-op.
    """

    def __init__(
        self,
        config: DatabricksConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("DatabricksPool requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DatabricksConfig | None:
        return self._config

    async def acquire(self) -> Any:
        return await self._ensure_client()

    async def release(self, connection: Any) -> None:
        return None

    async def close(self) -> None:
        if self._client is not None:
            close_fn = getattr(self._client, "close", None)
            if callable(close_fn):
                await asyncio.to_thread(close_fn)
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("databricks.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = list(parameters or ())

        def _run() -> Any:
            cursor = client.cursor()
            try:
                cursor.execute(query, params)
                return cursor.rowcount
            finally:
                cursor.close()

        return await asyncio.to_thread(_run)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = list(parameters or ())

        def _run() -> list[tuple[Any, ...]]:
            cursor = client.cursor()
            try:
                cursor.execute(query, params)
                return [tuple(r) for r in cursor.fetchall()]
            finally:
                cursor.close()

        return await asyncio.to_thread(_run)

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> Any:
        self._reject_inline_interpolation(query)
        client = await self._ensure_client()
        rows = [list(p) for p in parameter_seq]

        def _run() -> Any:
            cursor = client.cursor()
            try:
                cursor.executemany(query, rows)
                return cursor.rowcount
            finally:
                cursor.close()

        return await asyncio.to_thread(_run)

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("DatabricksPool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from databricks import sql as dbsql  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DatabricksPool requires databricks-sql-connector; install via "
                "`pip install pirn[databricks]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("DatabricksPool: missing config and no injected client")

        kwargs: dict[str, Any] = {}
        if self._config.server_hostname is not None:
            kwargs["server_hostname"] = self._config.server_hostname
        if self._config.http_path is not None:
            kwargs["http_path"] = self._config.http_path
        if self._config.access_token is not None:
            kwargs["access_token"] = self._config.access_token
        if self._config.catalog is not None:
            kwargs["catalog"] = self._config.catalog
        if self._config.schema is not None:
            kwargs["schema"] = self._config.schema
        try:
            client = await asyncio.to_thread(dbsql.connect, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("databricks.connect")
        return client
