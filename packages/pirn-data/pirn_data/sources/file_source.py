"""``FileSource`` — compose ``ObjectStore.get(key)`` with
``FileFormat.read`` to materialise a :class:`DataBatch`.

This is the universal "read a file from anywhere" knot. Compose any
:class:`ObjectStore` (S3, GCS, Azure Blob, local filesystem) with any
:class:`FileFormat` (Parquet, CSV, JSON, Avro, …) and the result is a
single pirn :class:`Source` that lands a :class:`DataBatch`.

For directory-style reads where the prefix matches many files, use
:class:`DirectorySource` instead.

Algorithm:
    1. Validate ``store`` (ObjectStore), ``format`` (FileFormat), ``key``
       (non-empty string), and optional ``schema`` (DataSchema) in
       ``process()``.
    2. Call ``await store.get(key)`` to fetch raw bytes.
    3. Pass the byte stream to ``await format.read(body)`` to decode
       records; collect them into a row list.
    4. Return a :class:`DataBatch` stamped with ``source_uri``,
       ``fetched_at=now(UTC)``, and the optional schema.

References:
    [1] :class:`pirn.connectors.object_store.ObjectStore` —
        pluggable storage backend abstraction.
    [2] :class:`pirn.connectors.file_format.FileFormat` —
        pluggable codec abstraction (Parquet, CSV, JSON, …).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema


class FileSource(Source):
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
        store: Knot | ObjectStore,
        format: Knot | FileFormat,
        key: Knot | str,
        schema: Knot | DataSchema | None = None,
        source_uri: Knot | str | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            format=format,
            key=key,
            schema=schema,
            source_uri=source_uri,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        key: str,
        schema: DataSchema | None = None,
        source_uri: str | None = None,
        **_: Any,
    ) -> DataBatch:
        if not isinstance(store, ObjectStore):
            raise TypeError("FileSource: store must be an ObjectStore instance")
        if not isinstance(format, FileFormat):
            raise TypeError("FileSource: format must be a FileFormat instance")
        if not isinstance(key, str) or not key:
            raise ValueError("FileSource: key must be a non-empty string")
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError("FileSource: schema must be a DataSchema instance")
        resolved_uri = source_uri or f"{type(store).__name__}://{key}"
        body = await store.get(key)
        records = await format.read(body)
        rows: list[dict[str, Any]] = []
        async for record in records:
            rows.append(dict(record))
        return DataBatch(
            rows=tuple(rows),
            schema=schema if schema is not None else DataSchema(),
            source_uri=resolved_uri,
            fetched_at=datetime.now(UTC),
        )
