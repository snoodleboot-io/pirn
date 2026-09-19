"""Sync Couchbase pool (wrapped in asyncio.to_thread) backed by the Couchbase SDK."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from contextlib import AbstractAsyncContextManager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.couchbase_config import CouchbaseConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.core.optional_dependency import OptionalDependency


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

    def transaction(self) -> AbstractAsyncContextManager[DatabaseConnectionPool]:
        """Refuse an atomic scope: Couchbase has none through this surface.

        Couchbase's distributed ACID transactions are a separate transactions API; the
        query surface this pool drives cannot enrol statements in one.

        Raises:
            NotImplementedError: Always. Issue the statements individually and
                make each one idempotent.
        """
        self._no_transaction_support("Couchbase", "the N1QL query surface")

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Execute a N1QL/SQL++ query; returns status string."""
        await self._ensure_cluster()
        if self._cluster is None:
            raise self._not_connected_error("CouchbasePool")
        result = await asyncio.to_thread(self._cluster.query, query, *tuple(parameters or ()))
        return str(result.meta_data().status)

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Execute a N1QL/SQL++ query and return all result rows."""
        await self._ensure_cluster()
        if self._cluster is None:
            raise self._not_connected_error("CouchbasePool")
        result = await asyncio.to_thread(self._cluster.query, query, *tuple(parameters or ()))
        return list(result.rows())

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Execute a N1QL/SQL++ query once per bind-value iterable."""
        for row in parameter_seq:
            await self.execute(query, row)

    async def _ensure_cluster(self) -> None:
        if self._closed:
            raise self._closed_error("CouchbasePool")
        if self._cluster is None:
            self._cluster = await asyncio.to_thread(self._create_cluster)

    def _create_cluster(self) -> Any:
        couchbase_auth = OptionalDependency.require("couchbase.auth", extra="couchbase")
        couchbase_cluster = OptionalDependency.require("couchbase.cluster", extra="couchbase")
        couchbase_options = OptionalDependency.require("couchbase.options", extra="couchbase")
        if self._config is None:
            raise self._missing_config_error("CouchbasePool", "cluster")

        try:
            auth = couchbase_auth.PasswordAuthenticator(
                self._config.username,
                self._config.password,
            )
            cluster: Any = couchbase_cluster.Cluster(
                self._config.connection_string,
                couchbase_options.ClusterOptions(auth),
            )
            cluster.wait_until_ready(timeout=self._config.kv_timeout_ms / 1000)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("couchbase.connect")
        return cluster
