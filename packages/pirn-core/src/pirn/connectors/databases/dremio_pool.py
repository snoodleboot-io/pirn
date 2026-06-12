"""Dremio Arrow Flight SQL connector wrapping ``pyarrow.flight``.

Arrow Flight is a synchronous gRPC-based protocol; all blocking calls are
dispatched via :func:`asyncio.to_thread`.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.databases.dremio_config import DremioConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class DremioPool(DatabaseConnectionPool):
    """Async Dremio pool backed by a ``pyarrow.flight.FlightClient``."""

    def __init__(
        self,
        config: DremioConfig | None = None,
        *,
        connection: Any = None,
    ) -> None:
        if config is None and connection is None:
            raise TypeError("DremioPool requires either config= or connection=")
        self._config = config
        self._connection = connection
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> DremioConfig | None:
        return self._config

    async def acquire(self) -> Any:
        conn = await self._ensure_connection()
        return conn

    async def release(self, connection: Any) -> None:
        pass

    async def close(self) -> None:
        if self._connection is not None:
            await asyncio.to_thread(self._connection.close)
            self._connection = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("dremio.close")

    async def execute(self, query: str, *args: Any) -> str:
        self._reject_inline_interpolation(query)
        connection = await self._ensure_connection()
        self._logger.debug("dremio.execute")
        return await asyncio.to_thread(self._run_action, connection, query)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        self._reject_inline_interpolation(query)
        connection = await self._ensure_connection()
        self._logger.debug("dremio.fetch_all")
        return await asyncio.to_thread(self._run_query, connection, query)

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        self._reject_inline_interpolation(query)
        for _ in args_seq:
            await self.execute(query)

    def _run_action(self, connection: Any, query: str) -> str:
        """Run a DDL/DML statement and return a row-count string."""
        action = type("FlightAction", (), {"type": "execute", "body": query.encode()})()
        results = list(connection.do_action(action))
        if results:
            return results[0].body.to_pybytes().decode()
        return "0"

    def _run_query(self, connection: Any, query: str) -> list[dict]:
        """Execute a SELECT and return rows as a list of dicts."""
        descriptor = type("FlightDescriptor", (), {"type": 1, "command": query.encode()})()
        flight_info = connection.get_flight_info(descriptor)
        rows: list[dict] = []
        for endpoint in flight_info.endpoints:
            reader = connection.do_get(endpoint.ticket)
            for batch in reader:
                table = batch.data
                columns = table.schema.names
                for i in range(table.num_rows):
                    rows.append({col: table.column(col)[i].as_py() for col in columns})
        return rows

    async def _ensure_connection(self) -> Any:
        if self._closed:
            raise RuntimeError("DremioPool is closed")
        if self._connection is None:
            self._connection = await self._create_connection()
        return self._connection

    async def _create_connection(self) -> Any:
        try:
            import pyarrow.flight as flight  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "DremioPool requires pyarrow; install via pip install pirn[dremio]"
            ) from exc
        if self._config is None:
            raise RuntimeError("DremioPool: missing config and no injected connection")

        config = self._config
        scheme = "grpc+tls" if config.tls else "grpc+tcp"
        location = f"{scheme}://{config.host}:{config.port}"

        def _connect() -> Any:
            import base64

            raw = f"{config.username}:{config.password}"
            encoded = base64.b64encode(raw.encode()).decode()
            options = flight.FlightCallOptions(  # type: ignore[attr-defined]
                headers=[(b"authorization", f"Basic {encoded}".encode())]
            )
            client = flight.FlightClient(location, generic_options=[])  # type: ignore[attr-defined]
            client._call_options = options
            return client

        try:
            conn = await asyncio.to_thread(_connect)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug(
            "dremio.connect", extra={"host": self._config.host, "port": self._config.port}
        )
        return conn
