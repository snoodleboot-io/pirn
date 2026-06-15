"""``FileSink`` — compose ``FileFormat.write`` with ``ObjectStore.put(key)``.

The universal "write a file anywhere" knot. Compose any
:class:`ObjectStore` (S3, GCS, Azure Blob, local filesystem) with any
:class:`FileFormat` (Parquet, CSV, JSON, …) and the result is a single
pirn :class:`Sink` that persists a :class:`DataBatch`.

Algorithm:
    1. Validate that ``store`` is an :class:`ObjectStore`, ``format`` is
       a :class:`FileFormat`, and ``key`` is a non-empty string.
    2. Wrap ``batch.rows`` in an async generator of row dicts and pass it
       to ``await format.write(records)`` to produce byte chunks.
    3. Concatenate all chunks into a single ``bytes`` payload.
    4. Call ``await store.put(key, payload)`` to persist the file.
    5. Return ``key`` so downstream knots can chain metadata-update
       operations off the written path.

References:
    [1] :class:`pirn.connectors.object_store.ObjectStore` —
        ``put(key, body)`` interface.
    [2] :class:`pirn.connectors.file_format.FileFormat` —
        ``write(records)`` async-generator interface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.sink import Sink

from pirn_data.data_batch import DataBatch


class FileSink(Sink):
    """Encode a :class:`DataBatch` and put the resulting bytes into an
    object store under ``key``.

    Returns the ``key`` written to so downstream knots can chain
    metadata-update operations.
    """

    def __init__(
        self,
        *,
        batch: Knot,
        store: Knot | Any,
        format: Knot | Any,
        key: Knot | str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            store=store,
            format=format,
            key=key,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        batch: DataBatch,
        store: Any,
        format: Any,
        key: Any,
        **_: Any,
    ) -> str:
        if not isinstance(store, ObjectStore):
            raise TypeError("FileSink: store must be an ObjectStore instance")
        if not isinstance(format, FileFormat):
            raise TypeError("FileSink: format must be a FileFormat instance")
        if not isinstance(key, str) or not key:
            raise ValueError("FileSink: key must be a non-empty string")

        async def _records() -> AsyncIterator[Mapping[str, Any]]:
            for row in batch.rows:
                yield row

        body_chunks = await format.write(_records())
        chunks: list[bytes] = []
        async for chunk in body_chunks:
            chunks.append(chunk)
        payload = b"".join(chunks)
        await store.put(key, payload)
        return key
