"""Sync Couchbase pool (wrapped in asyncio.to_thread) backed by the Couchbase SDK."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.couchbase_config import CouchbaseConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class CouchbasePool(DatabaseConnectionPool):
    """Couchbase pool wrapping the sync SDK in asyncio.to_thread."""

    def __init__(
        self,
        config: CouchbaseConfig | None = None,
        *,
        cluster: Any = None,
    ) -> None:
        if config is None and cluster is None:
            raise TypeError("CouchbasePool requires either config= or cluster=")
        if config is not None and not isinstance(config, CouchbaseConfig):
            raise TypeError(
                f"CouchbasePool: config must be CouchbaseConfig, got {type(config).__name__}"
            )
        self._config = config
        self._cluster = cluster
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> CouchbaseConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_cluster()
        return self._cluster

    async def release(self, connection: Any) -> None:
        pass  # Couchbase SDK manages connections internally

    async def close(self) -> None:
        if self._cluster is not None:
            await asyncio.to_thread(self._cluster.close)
            self._cluster = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("couchbase.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a N1QL/SQL++ query; returns status string."""
        await self._ensure_cluster()
        if self._cluster is None:
            raise RuntimeError("CouchbasePool: not connected — call connect() first")
        result = await asyncio.to_thread(self._cluster.query, query, *args)
        return str(result.meta_data().status)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Execute a N1QL/SQL++ query and return all result rows."""
        await self._ensure_cluster()
        if self._cluster is None:
            raise RuntimeError("CouchbasePool: not connected — call connect() first")
        result = await asyncio.to_thread(self._cluster.query, query, *args)
        return list(result.rows())

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        """Execute a N1QL/SQL++ query for each args tuple in args_seq."""
        for args in args_seq:
            await self.execute(query, *args)

    async def _ensure_cluster(self) -> None:
        if self._closed:
            raise RuntimeError("CouchbasePool is closed")
        if self._cluster is None:
            self._cluster = await asyncio.to_thread(self._create_cluster)

    def _create_cluster(self) -> Any:
        try:
            from couchbase.auth import PasswordAuthenticator
            from couchbase.cluster import Cluster
            from couchbase.options import ClusterOptions
        except ImportError as exc:
            raise ImportError(
                "CouchbasePool requires couchbase; install via pip install pirn[couchbase]"
            ) from exc
        if self._config is None:
            raise RuntimeError("CouchbasePool: missing config and no injected cluster")

        try:
            auth = PasswordAuthenticator(
                self._config.username,
                self._config.password,
            )
            cluster = Cluster(
                self._config.connection_string,
                ClusterOptions(auth),
            )
            cluster.wait_until_ready(timeout=self._config.kv_timeout_ms / 1000)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("couchbase.connect")
        return cluster
