"""Connection pool wrapper around the synchronous :mod:`oracledb` driver.

The Oracle Python driver (``python-oracledb``) is synchronous; calls run
in a worker thread via :func:`asyncio.to_thread` so the connector
cooperates with pirn's async runtime without blocking the event loop on
long queries.

Parameter style: Oracle uses ``:name`` named binds. Both ``{...}`` brace
interpolation and ``%s``-style markers are rejected — pass parameters
through the driver's bind mechanism instead.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.oracle_config import OracleConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class OraclePool(DatabaseConnectionPool):
    """Single-client Oracle pool driven through ``asyncio.to_thread``.

    The injected ``client`` (or ``oracledb`` connection / session pool)
    is treated as opaque: ``acquire`` returns it, ``release`` is a no-op.
    Cursors are opened per call and closed eagerly.
    """

    def __init__(
        self,
        config: OracleConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("OraclePool requires either config= or client=")
        if config is not None and not isinstance(config, OracleConfig):
            raise TypeError(
                f"OraclePool: config must be an OracleConfig instance, got {type(config).__name__}"
            )
        self._config = config
        self._client = client
        self._closed = False
        # Oracle uses ``:name`` named binds. Reject brace interpolation
        # AND ``%s``-style markers (which would mask a port from another
        # dialect's client).
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> OracleConfig | None:
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
        self._logger.debug("oracle.close")

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
            raise RuntimeError("OraclePool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            import oracledb  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "OraclePool requires oracledb; install via `pip install pirn[oracle]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("OraclePool: missing config and no injected client")

        kwargs: dict[str, Any] = {
            "min": self._config.min_size,
            "max": self._config.max_size,
        }
        for name, key in (
            ("user", "user"),
            ("password", "password"),
            ("dsn", "dsn"),
            ("wallet_location", "wallet_location"),
        ):
            value = getattr(self._config, name)
            if value is not None:
                kwargs[key] = value
        try:
            client = await asyncio.to_thread(oracledb.create_pool, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("oracle.connect")
        return client
