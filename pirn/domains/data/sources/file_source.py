"""``FileSource`` — compose ``ObjectStore.get(key)`` with
``FileFormat.read`` to materialise a :class:`DataBatch`.

This is the universal "read a file from anywhere" knot. Compose any
:class:`ObjectStore` (S3, GCS, Azure Blob, local filesystem) with any
:class:`FileFormat` (Parquet, CSV, JSON, Avro, …) and the result is a
single pirn :class:`Knot` that lands a :class:`DataBatch`.

For directory-style reads where the prefix matches many files, use
:class:`DirectorySource` instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.connectors.file_format import FileFormat
from pirn.domains.connectors.object_store import ObjectStore
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema


class FileSource(Knot):
    """Read one file via ``ObjectStore`` + decode via ``FileFormat``.

    Constructor
    -----------
    store:
        Any :class:`ObjectStore` (S3, GCS, Azure, Local).
    format:
        Any :class:`FileFormat` (Parquet, CSV, JSON, …) — decodes the
        bytes returned by ``store.get(key)`` into records.
    key:
        The object key / path within the store.
    schema:
        Optional :class:`DataSchema`. When provided, the resulting
        :class:`DataBatch` carries it forward for downstream typed
        consumers.
    source_uri:
        Lineage hint. When ``None``, defaults to
        ``f"{type(store).__name__}://{key}"``.
    """

    def __init__(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        key: str,
        schema: DataSchema | None = None,
        source_uri: str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "FileSource: store must be an ObjectStore instance"
            )
        if not isinstance(format, FileFormat):
            raise TypeError(
                "FileSource: format must be a FileFormat instance"
            )
        if not isinstance(key, str) or not key:
            raise ValueError(
                "FileSource: key must be a non-empty string"
            )
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError(
                "FileSource: schema must be a DataSchema instance"
            )
        self._store = store
        self._format = format
        self._key = key
        self._schema = schema
        self._source_uri = source_uri or f"{type(store).__name__}://{key}"
        super().__init__(_config=_config, **kwargs)

    @property
    def key(self) -> str:
        return self._key

    @property
    def format_name(self) -> str:
        return self._format.name

    async def process(self, **_: Any) -> DataBatch:
        body = await self._store.get(self._key)
        records = await self._format.read(body)
        rows: list[dict[str, Any]] = []
        async for record in records:
            rows.append(dict(record))
        return DataBatch(
            rows=tuple(rows),
            schema=self._schema if self._schema is not None else DataSchema(),
            source_uri=self._source_uri,
            fetched_at=datetime.now(timezone.utc),
        )
