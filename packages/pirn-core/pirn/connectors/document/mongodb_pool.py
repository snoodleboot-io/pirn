"""Async MongoDB connection pool backed by :mod:`motor`."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Iterable
from contextlib import asynccontextmanager
from typing import Any

from pirn.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.connectors.document.mongodb_config import MongoDBConfig
from pirn.connectors.dsn_scrubber import DsnScrubber
from pirn.connectors.mongodb_transaction import MongodbTransaction
from pirn.core.optional_dependency import OptionalDependency


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

    async def execute(self, query: str, parameters: Iterable[Any] | None = None) -> str:
        """Insert a document into ``query`` collection; returns inserted_id."""
        db = await self.acquire()
        doc: Iterable[Any] = parameters if parameters is not None else {}
        result = await db[query].insert_one(doc)
        return str(result.inserted_id)

    async def fetch_all(self, query: str, parameters: Iterable[Any] | None = None) -> list[Any]:
        """Fetch all documents from ``query`` collection matching optional filter."""
        db = await self.acquire()
        filter_doc: Iterable[Any] = parameters if parameters is not None else {}
        cursor = db[query].find(filter_doc)
        rows = await cursor.to_list(length=None)
        return [{k: v for k, v in doc.items() if k != "_id"} for doc in rows]

    async def execute_many(self, query: str, parameter_seq: Iterable[Iterable[Any]]) -> None:
        """Bulk-insert documents into ``query`` collection."""
        db = await self.acquire()
        docs = list(parameter_seq)
        await db[query].insert_many(docs)

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[DatabaseConnectionPool]:
        """Run the block's operations as one MongoDB multi-document transaction.

        Starts a client session, opens a transaction on it and yields a
        :class:`MongodbTransaction` bound to the database handle and that session.
        A clean exit commits; an exception aborts and propagates. The session ends
        either way.

        MongoDB serves multi-document transactions on replica sets and sharded
        clusters only; on a standalone ``mongod`` the driver raises when the
        transaction starts. That error is left to propagate rather than downgraded
        to a scope that would not be atomic.
        """
        client = await self._ensure_client()
        database = await self.acquire()
        session = await client.start_session()
        try:
            session.start_transaction()
            handle = MongodbTransaction((database, session), self)
            try:
                try:
                    yield handle
                except BaseException:
                    await session.abort_transaction()
                    raise
                await session.commit_transaction()
            finally:
                handle.finish()
        finally:
            await session.end_session()

    async def _ensure_client(self) -> Any:
        if self._closed:
            raise self._closed_error("MongoDBPool")
        if self._client is None:
            self._client = await self._create_client()
        return self._client

    async def _create_client(self) -> Any:
        motor_asyncio = OptionalDependency.require("motor.motor_asyncio", extra="mongodb")
        if self._config is None:
            raise self._missing_config_error("MongoDBPool", "client")

        uri = self._config.uri
        if uri == type(self)._default_uri and (self._config.username or self._config.password):
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
                client: Any = motor_asyncio.AsyncIOMotorClient(**kwargs)
            else:
                client = motor_asyncio.AsyncIOMotorClient(uri, **kwargs)
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("mongodb.connect")
        return client
