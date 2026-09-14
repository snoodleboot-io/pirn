"""Connection pool wrapper around the synchronous ``clickhouse_connect`` client.

``clickhouse_connect`` is synchronous; calls run in a worker thread via
:func:`asyncio.to_thread` so the connector cooperates with pirn's async
runtime without blocking the event loop on long queries.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.clickhouse_config import ClickhouseConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.optional_dependency import OptionalDependency
from pirn.core.shape_guard import ShapeGuard


class ClickhousePool(DatabaseConnectionPool):
    """Single-client ClickHouse pool.

    The ``clickhouse_connect.Client`` already manages an HTTP connection
    pool internally; ``acquire`` returns the shared client and ``release``
    is a no-op.

    Parameter style: ClickHouse uses ``{name:Type}`` parameterised
    queries — that is the driver's bind syntax, not interpolation, so
    brace markers are accepted. ``%s`` interpolation is still rejected.
    """

    _inline_interpolation_pattern = r"\{[^}:]+\}|%[sd]"

    def __init__(
        self,
        config: ClickhouseConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("ClickhousePool requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ClickhouseConfig | None:
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
        self._logger.debug("clickhouse.close")

    async def execute(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> Any:
        """Run a parameterised statement.

        ClickHouse uses named parameters (``{name:Type}``) — for safety we
        accept a mapping or sequence and forward it via the client's
        ``parameters`` keyword argument so the driver handles escaping.
        """
        self.reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = self._normalise_params(parameters)
        return await asyncio.to_thread(self._sync_execute, client, query, params)

    @staticmethod
    def _sync_execute(
        client: Any, query: str, params: Mapping[str, object] | list[Any] | None
    ) -> Any:
        return client.command(query, parameters=params)

    async def fetch_all(
        self,
        query: str,
        parameters: Iterable[Any] | None = None,
    ) -> list[tuple[Any, ...]]:
        self.reject_inline_interpolation(query)
        client = await self._ensure_client()
        params = self._normalise_params(parameters)
        return await asyncio.to_thread(self._sync_fetch_all, client, query, params)

    @staticmethod
    def _sync_fetch_all(
        client: Any, query: str, params: Mapping[str, object] | list[Any] | None
    ) -> list[tuple[Any, ...]]:
        result = client.query(query, parameters=params)
        rows = getattr(result, "result_rows", None)
        if rows is None:
            rows = list(result)
        return [tuple(r) for r in rows]

    async def execute_many(
        self,
        query: str,
        parameter_seq: Iterable[Iterable[Any]],
    ) -> None:
        """Bulk-insert via ``Client.insert`` when possible.

        ClickHouse's HTTP interface has no native ``executemany``; the
        driver's :meth:`Client.insert` is the supported batched path.
        Callers that want per-row ``execute`` repetition can loop over
        :meth:`execute` themselves.
        """
        self.reject_inline_interpolation(query)
        client = await self._ensure_client()
        rows = [list(p) for p in parameter_seq]
        await asyncio.to_thread(self._sync_execute_many, client, query, rows)

    @staticmethod
    def _sync_execute_many(client: Any, query: str, rows: list[Any]) -> None:
        insert_fn = getattr(client, "insert", None)
        if callable(insert_fn):
            insert_fn(query, rows)
            return
        for params in rows:
            client.command(query, parameters=params)

    @staticmethod
    def _normalise_params(
        parameters: Iterable[Any] | None,
    ) -> Mapping[str, object] | list[Any] | None:
        if parameters is None:
            return None
        if ShapeGuard.is_str_keyed_dict(parameters):
            return parameters
        # Sequences — forward as a list. The driver converts as needed.
        return list(parameters)

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise self._closed_error("ClickhousePool")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        clickhouse_connect = OptionalDependency.require("clickhouse_connect", extra="clickhouse")
        if self._config is None:
            raise self._missing_config_error("ClickhousePool", "client")

        kwargs: dict[str, Any] = {
            "host": self._config.host,
            "port": self._config.port,
            "secure": self._config.secure,
        }
        if self._config.username is not None:
            kwargs["username"] = self._config.username
        if self._config.password is not None:
            kwargs["password"] = self._config.password
        if self._config.database is not None:
            kwargs["database"] = self._config.database
        try:
            client: Any = await asyncio.to_thread(clickhouse_connect.get_client, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("clickhouse.connect")
        return client
