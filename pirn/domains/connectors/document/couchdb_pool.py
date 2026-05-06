"""Async CouchDB pool backed by :mod:`aiocouch`."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.couchdb_config import CouchDBConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class CouchDBPool(DatabaseConnectionPool):
    """Async CouchDB pool using aiocouch."""

    def __init__(
        self,
        config: CouchDBConfig | None = None,
        *,
        session: Any = None,
    ) -> None:
        if config is None and session is None:
            raise TypeError("CouchDBPool requires either config= or session=")
        if config is not None and not isinstance(config, CouchDBConfig):
            raise TypeError(
                f"CouchDBPool: config must be CouchDBConfig, got {type(config).__name__}"
            )
        self._config = config
        self._session = session
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> CouchDBConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_session()
        return self._session

    async def release(self, connection: Any) -> None:
        pass  # aiocouch manages connections internally

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("couchdb.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Save a document; ``query`` is the doc id, ``args[0]`` is the doc dict.

        Returns the document ``_id``.
        """
        await self._ensure_session()
        assert self._config is not None
        doc_data = args[0] if args else {}
        db = await self._session[self._config.database]
        doc = await db.create(query, data=doc_data)
        await doc.save()
        return doc["_id"]

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Fetch documents via Mango selector; ``query`` is a JSON selector string."""
        await self._ensure_session()
        assert self._config is not None
        try:
            selector = json.loads(query)
        except (json.JSONDecodeError, TypeError):
            selector = {"_id": {"$gt": None}}
        db = await self._session[self._config.database]
        result = await db.find(selector)
        return list(result)

    async def execute_many(
        self, query: str, args_seq: Iterable[Iterable[Any]]
    ) -> None:
        """Bulk-save documents via _bulk_docs."""
        await self._ensure_session()
        assert self._config is not None
        db = await self._session[self._config.database]
        docs = list(args_seq)
        await db.bulk_docs(docs)

    async def _ensure_session(self) -> None:
        if self._closed:
            raise RuntimeError("CouchDBPool is closed")
        if self._session is None:
            self._session = await self._create_session()

    async def _create_session(self) -> Any:
        try:
            import aiocouch
        except ImportError as exc:
            raise ImportError(
                "CouchDBPool requires aiocouch; install via pip install pirn[couchdb]"
            ) from exc
        if self._config is None:
            raise RuntimeError("CouchDBPool: missing config and no injected session")

        try:
            session = aiocouch.CouchDB(
                self._config.url,
                user=self._config.username,
                password=self._config.password,
            )
            await session.open()
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("couchdb.connect")
        return session
