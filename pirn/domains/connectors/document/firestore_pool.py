"""Async Google Cloud Firestore pool backed by :mod:`google.cloud.firestore_v1`."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

from pirn.domains.connectors.database_connection_pool import DatabaseConnectionPool
from pirn.domains.connectors.document.firestore_config import FirestoreConfig
from pirn.domains.connectors.dsn_scrubber import DsnScrubber


class FirestorePool(DatabaseConnectionPool):
    """Async Firestore pool using google-cloud-firestore AsyncClient."""

    def __init__(
        self,
        config: FirestoreConfig | None = None,
        *,
        client: Any = None,
    ) -> None:
        if config is None and client is None:
            raise TypeError("FirestorePool requires either config= or client=")
        if config is not None and not isinstance(config, FirestoreConfig):
            raise TypeError(
                f"FirestorePool: config must be FirestoreConfig, got {type(config).__name__}"
            )
        self._config = config
        self._client = client
        self._closed = False
        self._scrubber = DsnScrubber()
        self._logger = logging.getLogger(self.__class__.__module__)

    @property
    def config(self) -> FirestoreConfig | None:
        return self._config

    async def acquire(self) -> Any:
        await self._ensure_client()
        return self._client

    async def release(self, connection: Any) -> None:
        pass  # Firestore async client manages connections internally

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None
        self._clear_credentials()
        self._closed = True
        self._logger.debug("firestore.close")

    async def execute(self, query: str, *args: Any) -> str:
        """Add a document to ``query`` collection; ``args[0]`` is the doc dict.

        Returns the new document id.
        """
        await self._ensure_client()
        doc_data = args[0] if args else {}
        _timestamp, doc_ref = await self._client.collection(query).add(doc_data)
        return doc_ref.id

    async def fetch_all(self, query: str, *args: Any) -> list[Any]:
        """Fetch documents from ``query`` collection path.

        ``args[0]`` is an optional filter dict (field equality filters).
        """
        await self._ensure_client()
        col_ref = self._client.collection(query)
        if args and isinstance(args[0], dict):
            for field, value in args[0].items():
                col_ref = col_ref.where(field, "==", value)
        docs = col_ref.stream()
        return [doc.to_dict() async for doc in docs]

    async def execute_many(self, query: str, args_seq: Iterable[Iterable[Any]]) -> None:
        """Batch-write documents to ``query`` collection."""
        await self._ensure_client()
        batch = self._client.batch()
        col_ref = self._client.collection(query)
        for args in args_seq:
            doc_data = args if isinstance(args, dict) else (next(iter(args)) if args else {})
            doc_ref = col_ref.document()
            batch.set(doc_ref, doc_data)
        await batch.commit()

    async def _ensure_client(self) -> None:
        if self._closed:
            raise RuntimeError("FirestorePool is closed")
        if self._client is None:
            self._client = await self._create_client()

    async def _create_client(self) -> Any:
        try:
            from google.cloud.firestore_v1.async_client import AsyncClient
        except ImportError as exc:
            raise ImportError(
                "FirestorePool requires google-cloud-firestore; "
                "install via pip install pirn[firestore]"
            ) from exc
        if self._config is None:
            raise RuntimeError("FirestorePool: missing config and no injected client")

        try:
            credentials = None
            if self._config.credentials_json:
                import json

                from google.oauth2 import service_account

                try:
                    cred_info = json.loads(self._config.credentials_json)
                except json.JSONDecodeError:
                    cred_info = None

                if cred_info:
                    credentials = service_account.Credentials.from_service_account_info(cred_info)

            firestore_client = AsyncClient(
                project=self._config.project_id,
                credentials=credentials,
                database=self._config.database_id,
            )
        except Exception as exc:
            self._reraise_scrubbed(exc)
        self._logger.debug("firestore.connect")
        return firestore_client
