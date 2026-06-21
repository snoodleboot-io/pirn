"""Sync ArangoDB pool (wrapped in asyncio.to_thread) backed by :mod:`arango`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.arangodb_config import ArangoDBConfig
from pirn.connectors.dsn_scrubber import DsnScrubber


class ArangoDBPool(DatabaseConnectionPool):
    """ArangoDB pool wrapping python-arango in asyncio.to_thread."""

    def __init__(
        self,
        config: ArangoDBConfig | None = None,
        *,
        db: Any = None,
    ) -> None:
        if config is None and db is None:
            raise TypeError("ArangoDBPool requires either config= or db=")
        if config is not None and not isinstance(config, ArangoDBConfig):
            raise TypeError(
                f"ArangoDBPool: config must be ArangoDBConfig, got {type(config).__name__}"
            )
        self._config = config
        self._db = db
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> ArangoDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_db()
        return self._db

    async def release(self, connection: Any) -> None:
        pass  # python-arango manages connections internally

    async def close(self) -> None:
        self._clear_credentials()
        self._closed = True
        self._logger.debug("arangodb.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Execute an AQL query; returns cursor result as str."""
        await self._ensure_db()
        bind_vars = args[0] if args else {}
        cursor = await asyncio.to_thread(self._db.aql.execute, query, bind_vars=bind_vars)
        return str(cursor)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Execute an AQL query and return all result documents."""
        await self._ensure_db()
        bind_vars = args[0] if args else {}
        cursor = await asyncio.to_thread(self._db.aql.execute, query, bind_vars=bind_vars)
        return list(cursor)

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        """Execute an AQL query for each bind_vars dict in args_seq."""
        for bind_vars in args_seq:
            await self.execute(query, bind_vars)

    async def _ensure_db(self) -> None:
        if self._closed:
            raise RuntimeError("ArangoDBPool is closed")
        if self._db is None:
            self._db = await asyncio.to_thread(self._create_db)

    def _create_db(self) -> Any:
        try:
            from arango import ArangoClient
        except ImportError as exc:
            raise ImportError(
                "ArangoDBPool requires python-arango; install via pip install pirn[arangodb]"
            ) from exc
        if self._config is None:
            raise RuntimeError("ArangoDBPool: missing config and no injected db")

        try:
            client = ArangoClient(
                hosts=self._config.url,
                verify_override=self._config.verify_ssl,
            )
            db = client.db(
                self._config.database,
                username=self._config.username,
                password=self._config.password,
                verify=True,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("arangodb.connect")
        return db
