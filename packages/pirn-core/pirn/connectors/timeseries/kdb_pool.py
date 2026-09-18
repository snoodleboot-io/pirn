"""Async kdb+ pool backed by :mod:`pykx`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.timeseries.kdb_config import KdbConfig
from pirn.core.optional_dependency import OptionalDependency


class KdbPool(DatabaseConnectionPool):
    """Async kdb+ pool; sync SDK calls are wrapped in :func:`asyncio.to_thread`."""

    def __init__(
        self,
        config: KdbConfig | None = None,
        *,
        connection: Any = None,
    ) -> None:
        if config is None and connection is None:
            raise TypeError("KdbPool requires either config= or connection=")
        self._config = config
        self._connection = connection
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> KdbConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_connection()
        return self._connection

    async def release(self, connection: Any) -> None:
        pass

    async def close(self) -> None:
        if self._connection is not None:
            await asyncio.to_thread(self._connection.close)
            self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("kdb.close")

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        await self._ensure_connection()
        if self._connection is None:
            raise self._not_connected_error("KdbPool")
        try:
            result = await asyncio.to_thread(self._connection.sync, query, *tuple(parameters or ()))
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return str(result)

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        await self._ensure_connection()
        if self._connection is None:
            raise self._not_connected_error("KdbPool")
        try:
            result = await asyncio.to_thread(self._connection.sync, query, *tuple(parameters or ()))
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return self._to_rows(result)

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        await self._ensure_connection()
        if self._connection is None:
            raise self._not_connected_error("KdbPool")
        for row in parameter_seq:
            try:
                await asyncio.to_thread(self._connection.sync, query, *tuple(row))
            except Exception as exc:
                self._reraise_scrubbed(exc)

    def _to_rows(self, result: Any) -> list[Any]:
        """Convert a kdb+ table result to a list of dicts.

        pykx tables are iterable collections of dict-like rows; scalar or
        non-table results are wrapped in a single-element list.
        """
        if result is None:
            return []
        # Only attempt dict conversion when the result is a non-string iterable
        # whose elements are themselves mappings (dict-like rows).
        if not isinstance(result, (str, bytes)) and hasattr(result, "__iter__"):
            try:
                rows = [dict(row) for row in result]
                return rows
            except (TypeError, ValueError, AttributeError):
                pass
        return [result]

    async def _ensure_connection(self) -> None:
        if self._closed:
            raise self._closed_error("KdbPool")
        if self._connection is None:
            self._connection = await self._create_connection()

    async def _create_connection(self) -> Any:
        if self._config is None:
            raise self._missing_config_error("KdbPool", "connection")
        try:
            connection = await asyncio.to_thread(self._connect_sync, self._config)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("kdb.connect")
        return connection

    @staticmethod
    def _connect_sync(config: KdbConfig) -> Any:
        """Synchronous connection attempt; called inside :func:`asyncio.to_thread`."""
        pykx = OptionalDependency.require("pykx", extra="kdb")
        return pykx.SyncQConnection(
            host=config.host,
            port=config.port,
            username=config.username or None,
            password=config.password or None,
            timeout=config.timeout,
            tls=config.tls,
        )
