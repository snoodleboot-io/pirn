"""Async kdb+ pool backed by :mod:`pykx` (with :mod:`qpython` fallback)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.timeseries.kdb_config import KdbConfig


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

    async def execute(self, query: str, *args: Any) -> str:
        await self._ensure_connection()
        try:
            result = await asyncio.to_thread(self._connection.sync, query, *args)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return str(result)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        await self._ensure_connection()
        try:
            result = await asyncio.to_thread(self._connection.sync, query, *args)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return self._to_rows(result)

    async def execute_many(
        self, query: str, args_seq: Iterable[Iterable[Any]]
    ) -> None:
        await self._ensure_connection()
        for args in args_seq:
            try:
                await asyncio.to_thread(self._connection.sync, query, *args)
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
            raise RuntimeError("KdbPool is closed")
        if self._connection is None:
            self._connection = await self._create_connection()

    async def _create_connection(self) -> Any:
        if self._config is None:
            raise RuntimeError(
                "KdbPool: missing config and no injected connection"
            )
        try:
            connection = await asyncio.to_thread(
                self._connect_sync, self._config
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("kdb.connect")
        return connection

    @staticmethod
    def _connect_sync(config: KdbConfig) -> Any:
        """Synchronous connection attempt; called inside :func:`asyncio.to_thread`."""
        try:
            import pykx

            return pykx.SyncQConnection(
                host=config.host,
                port=config.port,
                username=config.username or None,
                password=config.password or None,
                timeout=config.timeout,
                tls=config.tls,
            )
        except ImportError as _pykx_err:
            import logging as _logging
            _logging.getLogger(__name__).debug(
                "kdb: pykx not available (%s), trying qpython", _pykx_err
            )

        try:
            from qpython import qconnection

            conn = qconnection.QConnection(
                host=config.host,
                port=config.port,
                username=config.username or None,
                password=config.password or None,
                timeout=config.timeout,
            )
            conn.open()
            return conn
        except ImportError as exc:
            raise ImportError(
                "KdbPool requires pykx or qpython; install via "
                "`pip install pirn[kdb]`"
            ) from exc
