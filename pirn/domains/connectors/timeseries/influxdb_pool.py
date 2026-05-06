"""Async InfluxDB connection pool backed by :mod:`influxdb_client`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.timeseries.influxdb_config import InfluxDBConfig


class InfluxDBPool(DatabaseConnectionPool):
    """Async InfluxDB pool with credential-safe error reporting."""

    def __init__(
        self,
        config: InfluxDBConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("InfluxDBPool requires either config= or client=")
        self._config = config
        self._client = client
        self._write_api: Any = None
        self._query_api: Any = None
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> InfluxDBConfig | None:
        return self._config

    async def acquire(self) -> dict[str, Any]:
        await self._ensure_client()
        return {"write": self._write_api, "query": self._query_api}

    async def release(self, connection: Any) -> None:
        pass

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
            self._write_api = None
            self._query_api = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("influxdb.close")

    async def execute(self, query: str, *args: Any) -> str:
        await self._ensure_client()
        lines = [query] if isinstance(query, str) else list(query)
        try:
            await self._write_api.write(
                bucket=self._config.bucket if self._config else "",
                org=self._config.org if self._config else "",
                record=lines,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return "OK"

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        await self._ensure_client()
        org = self._config.org if self._config else ""
        try:
            tables = await self._query_api.query(query, org=org)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        rows: list[dict[str, Any]] = []
        for table in tables:
            for record in table.records:
                rows.append(dict(record.values))
        return rows

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        await self._ensure_client()
        lines = list(args_seq)
        try:
            await self._write_api.write(
                bucket=self._config.bucket if self._config else "",
                org=self._config.org if self._config else "",
                record=lines,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def _ensure_client(self) -> None:
        if self._closed:
            raise RuntimeError("InfluxDBPool is closed")
        if self._client is None:
            self._client = await self._create_client()
        if self._write_api is None:
            self._write_api = self._client.write_api()
        if self._query_api is None:
            self._query_api = self._client.query_api()

    async def _create_client(self) -> Any:
        try:
            from influxdb_client.client.influxdb_client_async import (
                InfluxDBClientAsync,
            )
        except ImportError as exc:
            raise ImportError(
                "InfluxDBPool requires influxdb-client; install via pip install pirn[influxdb]"
            ) from exc
        if self._config is None:
            raise RuntimeError("InfluxDBPool: missing config and no injected client")
        try:
            client = InfluxDBClientAsync(
                url=self._config.url,
                token=self._config.token,
                org=self._config.org,
                verify_ssl=self._config.verify_ssl,
                timeout=self._config.timeout,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("influxdb.connect")
        return client
