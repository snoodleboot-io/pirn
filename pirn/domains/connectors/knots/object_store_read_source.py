"""``ObjectStoreReadSource`` — a pirn :class:`Source` that reads bytes from
any :class:`ObjectStore` backend at a configured key.

This is a Layer-2 connector knot. It composes a Layer-1 backend
(``LocalFilesystemStore``, ``S3Store``, …) into the pirn pipeline as a
first-class :class:`Knot` — the Source has no parents and produces a
``bytes`` value its consumers can transform and sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.object_store import ObjectStore
from pirn.nodes.source import Source


class ObjectStoreReadSource(Source):
    """Source that reads ``key`` from an :class:`ObjectStore` backend.

    The full body is materialised into a single ``bytes`` value — for
    streaming reads (multi-GB), use a different knot (TBD) that yields
    chunks. For typical pipeline payloads (CSV, JSON, Parquet up to a few
    hundred MB) the simpler all-at-once contract is more convenient.
    """

    def __init__(
        self,
        *,
        store: ObjectStore,
        key: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreReadSource: store must be an ObjectStore, "
                f"got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError("ObjectStoreReadSource: key must be a non-empty string")
        self._store = store
        self._key = key
        super().__init__(_config=_config, **kwargs)

    @property
    def store(self) -> ObjectStore:
        return self._store

    @property
    def key(self) -> str:
        return self._key

    async def process(self, **_: Any) -> bytes:
        chunks: list[bytes] = []
        async for chunk in await self._store.get(self._key):
            chunks.append(chunk)
        return b"".join(chunks)
