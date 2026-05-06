"""Async MongoDB connection pool backed by :mod:`motor`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.mongodb_config import MongoDBConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class MongoDBPool(DatabaseConnectionPool):
    """Async MongoDB pool using Motor's AsyncIOMotorClient."""

    _default_uri: str = "mongodb://localhost:27017"

    def __init__(
        self,
        config: MongoDBConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("MongoDBPool requires either config= or client=")
        if config is not None and not isinstance(config, MongoDBConfig):
            raise TypeError(
                f"MongoDBPool: config must be MongoDBConfig, got {type(config).__name__}"
            )
        if config is not None and not config.database:
            raise ValueError("MongoDBPool: config.database must be non-empty")
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> MongoDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        client = await self._ensure_client()
        assert self._config is not None
        return client[self._config.database]

    async def release(self, connection: Any) -> None:
        pass  # Motor manages connections internally

    async def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("mongodb.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Insert a document into ``query`` collection; returns inserted_id."""
        db = await self.acquire()
        doc = args[0] if args else {}
        result = await db[query].insert_one(doc)
        return str(result.inserted_id)

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Fetch all documents from ``query`` collection matching optional filter."""
        db = await self.acquire()
        filter_doc = args[0] if args else {}
        cursor = db[query].find(filter_doc)
        rows = await cursor.to_list(length=None)
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in rows]

    async def execute_many(
        self, query: str, args_seq: Iterable[Iterable[Any]]
    ) -> None:
        """Bulk-insert documents into ``query`` collection."""
        db = await self.acquire()
        docs = list(args_seq)
        await db[query].insert_many(docs)

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise RuntimeError("MongoDBPool is closed")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient
        except ImportError as exc:
            raise ImportError(
                "MongoDBPool requires motor; install via pip install pirn[mongodb]"
            ) from exc
        if self._config is None:
            raise RuntimeError("MongoDBPool: missing config and no injected client")

        uri = self._config.uri
        if uri == type(self)._default_uri and (
            self._config.username or self._config.password
        ):
            # Build URI using driver kwargs instead of embedding creds in string
            uri = None  # signal to use explicit kwargs below

        try:
            kwargs: dict[str, Any] = {
                "tls": self._config.tls,
                "maxPoolSize": self._config.max_pool_size,
                "serverSelectionTimeoutMS": self._config.server_selection_timeout_ms,
            }
            if uri is None:
                # Pass credentials as explicit kwargs — never embedded in URI
                kwargs["host"] = self._config.host
                kwargs["port"] = self._config.port
                kwargs["username"] = self._config.username
                kwargs["password"] = self._config.password
                kwargs["authSource"] = self._config.auth_source
                client: Any = AsyncIOMotorClient(**kwargs)
            else:
                client = AsyncIOMotorClient(uri, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("mongodb.connect")
        return client
