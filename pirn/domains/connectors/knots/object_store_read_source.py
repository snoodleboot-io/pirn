"""``ObjectStoreReadSource`` — a pirn :class:`Source` that reads bytes from
any :class:`ObjectStore` backend at a configured key.

This is a Layer-2 connector knot. It composes a Layer-1 backend
(``LocalFilesystemStore``, ``S3Store``, …) into the pirn pipeline as a
first-class :class:`Knot` — the Source has no parents and produces a
``bytes`` value its consumers can transform and sink.

Algorithm:
    1. Validate that ``store`` is an :class:`ObjectStore` and ``key``
       is a non-empty string.
    2. Call ``await store.get(key)`` to obtain an async iterator of byte chunks.
    3. Concatenate all chunks and return the complete bytes value.


References:
    - :class:`pirn.domains.connectors.object_store.ObjectStore`
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.knots.object_store_knot import ObjectStoreKnot
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
        store: ObjectStoreKnot,
        key: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(store=store, key=key, _config=_config, **kwargs)

    async def process(self, store: ObjectStore, key: str, **_: Any) -> bytes:
        """Read all bytes from the configured object-store key and return them.

        Args:
            store: The object store to read from.
            key: The key of the object to read.

        Returns:
            The complete bytes content of the object at the configured key.

        Raises:
            TypeError: If store is not an ObjectStore.
            ValueError: If key is empty.
        """
        if not isinstance(store, ObjectStore):
            raise TypeError(
                f"ObjectStoreReadSource: store must be an ObjectStore, got {type(store).__name__}"
            )
        if not isinstance(key, str) or not key:
            raise ValueError("ObjectStoreReadSource: key must be a non-empty string")
        chunks: list[bytes] = []
        async for chunk in await store.get(key):
            chunks.append(chunk)
        return b"".join(chunks)
