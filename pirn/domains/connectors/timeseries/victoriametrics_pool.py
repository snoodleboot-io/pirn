"""Async VictoriaMetrics pool backed by :mod:`httpx`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.dsn_scrubber import DsnScrubber
from pirn.domains.connectors.timeseries.victoriametrics_config import (
    VictoriaMetricsConfig,
)


class VictoriaMetricsPool(DatabaseConnectionPool):
    """Async VictoriaMetrics pool using Prometheus-compatible HTTP endpoints."""

    def __init__(
        self,
        config: VictoriaMetricsConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("VictoriaMetricsPool requires either config= or client=")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> VictoriaMetricsConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_client()
        return self._client

    async def release(self, connection: Any) -> None:
        pass

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("victoriametrics.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Write metrics in Prometheus exposition format via remote write."""
        await self._ensure_client()
        if self._client is None:
            raise RuntimeError("VictoriaMetricsPool: not connected — call connect() first")
        try:
            response = await self._client.post(
                "/api/v1/import/prometheus",
                content=query,
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return "OK"

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Execute a MetricsQL/PromQL instant query."""
        await self._ensure_client()
        if self._client is None:
            raise RuntimeError("VictoriaMetricsPool: not connected — call connect() first")
        try:
            response = await self._client.get(
                "/api/v1/query",
                params={"query": query},
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            self._reraise_scrubbed(exc)
        return list(data.get("data", {}).get("result", []))

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        """Write multiple metric lines as a single remote write batch."""
        await self._ensure_client()
        if self._client is None:
            raise RuntimeError("VictoriaMetricsPool: not connected — call connect() first")
        lines = "\n".join(str(item) for row in args_seq for item in row)
        try:
            response = await self._client.post(
                "/api/v1/import/prometheus",
                content=lines,
                headers={"Content-Type": "text/plain"},
            )
            response.raise_for_status()
        except Exception as exc:
            self._reraise_scrubbed(exc)

    async def _ensure_client(self) -> None:
        if self._closed:
            raise RuntimeError("VictoriaMetricsPool is closed")
        if self._client is None:
            self._client = await self._create_client()

    async def _create_client(self) -> Any:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "VictoriaMetricsPool requires httpx; install via "
                "`pip install pirn[victoriametrics]`"
            ) from exc
        if self._config is None:
            raise RuntimeError("VictoriaMetricsPool: missing config and no injected client")
        auth = None
        if self._config.username is not None:
            auth = (self._config.username, self._config.password or "")
        try:
            client = httpx.AsyncClient(
                base_url=self._config.url,
                auth=auth,
                verify=self._config.verify_ssl,
                timeout=self._config.timeout,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("victoriametrics.connect")
        return client
