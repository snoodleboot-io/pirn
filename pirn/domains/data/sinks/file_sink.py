"""``FileSink`` — compose ``FileFormat.write`` with ``ObjectStore.put(key)``.

The universal "write a file anywhere" knot. Compose any
:class:`ObjectStore` (S3, GCS, Azure Blob, local filesystem) with any
:class:`FileFormat` (Parquet, CSV, JSON, …) and the result is a single
pirn :class:`Knot` that persists a :class:`DataBatch`.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Mapping

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.data.data_batch import DataBatch


class FileSink(Knot):
    """Encode a :class:`DataBatch` and put the resulting bytes into an
    object store under ``key``.

    Returns the ``key`` written to so downstream knots can chain
    metadata-update operations.
    """

    def __init__(
        self,
        *,
        batch: Knot,
        store: ObjectStore,
        format: FileFormat,
        key: str,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "FileSink: store must be an ObjectStore instance"
            )
        if not isinstance(format, FileFormat):
            raise TypeError(
                "FileSink: format must be a FileFormat instance"
            )
        if not isinstance(key, str) or not key:
            raise ValueError("FileSink: key must be a non-empty string")
        self._store = store
        self._format = format
        self._key = key
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def key(self) -> str:
        return self._key

    @property
    def format_name(self) -> str:
        return self._format.name

    async def process(self, batch: DataBatch, **_: Any) -> str:
        async def _records() -> AsyncIterator[Mapping[str, Any]]:
            for row in batch.rows:
                yield row

        body_chunks = await self._format.write(_records())
        chunks: list[bytes] = []
        async for chunk in body_chunks:
            chunks.append(chunk)
        payload = b"".join(chunks)
        await self._store.put(self._key, payload)
        return self._key
