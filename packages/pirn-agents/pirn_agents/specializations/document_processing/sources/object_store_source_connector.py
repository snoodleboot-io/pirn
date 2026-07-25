"""``ObjectStoreSourceConnector`` — pull documents from object storage (F25-S3 / PIR-609).

Built on the core :class:`~pirn.connectors.object_store.ObjectStore` interface
(local filesystem or S3-compatible), it lists the keys under a prefix, streams
each object's bytes, dedups by content hash, and yields a
:class:`~pirn_agents.specializations.document_processing.sources.source_document.SourceDocument`.
A read failure on one key (auth, network, missing object) is recorded on
:attr:`errors` and skipped rather than aborting the whole crawl. The backend SDK
is lazily imported by the concrete blob store, so this module pulls no backend.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from pirn.connectors.object_store import ObjectStore

from pirn_agents.specializations.document_processing.sources.content_hash_deduplicator import (
    ContentHashDeduplicator,
)
from pirn_agents.specializations.document_processing.sources.source_connector import (
    SourceConnector,
)
from pirn_agents.specializations.document_processing.sources.source_document import (
    SourceDocument,
)


class ObjectStoreSourceConnector(SourceConnector):
    """Stream objects under a prefix from an :class:`ObjectStore`, deduped by hash."""

    def __init__(
        self,
        *,
        blob_store: ObjectStore,
        prefix: str = "",
        deduplicator: ContentHashDeduplicator | None = None,
    ) -> None:
        """Bind the connector to a blob store and prefix.

        Args:
            blob_store: The core object-storage backend to read from.
            prefix: Key prefix limiting which objects are ingested.
            deduplicator: Optional shared content-hash deduplicator; when
                ``None`` a fresh one is created.

        Raises:
            TypeError: If ``blob_store`` is not an :class:`ObjectStore`.
        """
        if not isinstance(blob_store, ObjectStore):
            raise TypeError(
                f"ObjectStoreSourceConnector: blob_store must be an ObjectStore, "
                f"got {type(blob_store).__name__}"
            )
        self._blob_store = blob_store
        self._prefix = prefix
        self._deduplicator = deduplicator if deduplicator is not None else ContentHashDeduplicator()
        self._errors: list[tuple[str, str]] = []

    async def fetch(self) -> AsyncIterator[SourceDocument]:
        """Yield each new object under the prefix as a :class:`SourceDocument`.

        Yields:
            One :class:`SourceDocument` per distinct-content object; duplicates
            and unreadable keys are skipped (the latter recorded on
            :attr:`errors`).
        """
        self._errors = []
        async for key in await self._blob_store.list(self._prefix):
            try:
                data = b"".join([chunk async for chunk in await self._blob_store.get(key)])
            except Exception as exc:
                self._errors.append((key, str(exc)))
                continue
            if not self._deduplicator.is_new(data):
                continue
            yield SourceDocument.create(
                source_id=key, data=data, metadata={"source": "object_store"}
            )

    @property
    def errors(self) -> tuple[tuple[str, str], ...]:
        """Return the ``(key, error)`` pairs skipped during the last fetch."""
        return tuple(self._errors)
