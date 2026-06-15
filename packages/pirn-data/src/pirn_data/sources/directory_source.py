"""``DirectorySource`` — read every file under a prefix.

Lists object keys via ``ObjectStore.list(prefix)``, decodes each via
the supplied :class:`FileFormat`, and emits either:

* one :class:`DataBatch` per file (default), as a tuple
  ``tuple[DataBatch, ...]``, or
* a single concatenated :class:`DataBatch` when ``concatenate=True``.

The per-file shape preserves provenance — each batch's ``source_uri``
points at its individual key — at the cost of downstream knots having
to handle a tuple. The concatenated shape is convenient for "load all
my parquet shards" use cases but loses per-file lineage.

Algorithm:
    1. Validate ``store``, ``format``, ``prefix``, and optional ``schema``
       in ``process()``.
    2. Call ``await store.list(prefix)`` and collect all matching keys;
       sort them for deterministic ordering.
    3. For each key, fetch bytes via ``store.get(key)`` and decode via
       ``format.read(body)``; build one :class:`DataBatch` per file,
       each stamped with its own ``source_uri``.
    4. If ``concatenate=False``, return the per-file batches as a tuple.
    5. If ``concatenate=True``, concatenate all rows into a single
       :class:`DataBatch` with a glob ``source_uri``.

References:
    [1] :class:`pirn.connectors.object_store.ObjectStore` —
        ``list(prefix)`` and ``get(key)`` interface.
    [2] :class:`pirn.connectors.file_format.FileFormat` —
        pluggable codec abstraction.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from pirn.connectors.file_format import FileFormat
from pirn.connectors.object_store import ObjectStore
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.nodes.source import Source

from pirn_data.data_batch import DataBatch
from pirn_data.data_schema import DataSchema


class DirectorySource(Source):
    """Glob a prefix; emit one :class:`DataBatch` per file (or one
    concatenated batch when ``concatenate=True``)."""

    def __init__(
        self,
        *,
        store: Knot | ObjectStore,
        format: Knot | FileFormat,
        prefix: Knot | str,
        concatenate: Knot | bool = False,
        schema: Knot | DataSchema | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            store=store,
            format=format,
            prefix=prefix,
            concatenate=concatenate,
            schema=schema,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        prefix: str,
        concatenate: bool = False,
        schema: DataSchema | None = None,
        **_: Any,
    ) -> tuple[DataBatch, ...] | DataBatch:
        if not isinstance(store, ObjectStore):
            raise TypeError("DirectorySource: store must be an ObjectStore instance")
        if not isinstance(format, FileFormat):
            raise TypeError("DirectorySource: format must be a FileFormat instance")
        if not isinstance(prefix, str):
            raise TypeError("DirectorySource: prefix must be a string (use '' for root)")
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError("DirectorySource: schema must be a DataSchema instance")
        keys: list[str] = []
        key_iter = await store.list(prefix)
        async for k in key_iter:
            keys.append(k)
        keys.sort()

        per_file_batches: list[DataBatch] = []
        for k in keys:
            body = await store.get(k)
            records = await format.read(body)
            rows: list[dict[str, Any]] = []
            async for record in records:
                rows.append(dict(record))
            per_file_batches.append(
                DataBatch(
                    rows=tuple(rows),
                    schema=(schema if schema is not None else DataSchema()),
                    source_uri=f"{type(store).__name__}://{k}",
                    fetched_at=datetime.now(UTC),
                )
            )

        if not concatenate:
            return tuple(per_file_batches)

        all_rows: list[Mapping[str, Any]] = []
        for batch in per_file_batches:
            all_rows.extend(batch.rows)
        return DataBatch(
            rows=tuple(all_rows),
            schema=(schema if schema is not None else DataSchema()),
            source_uri=f"{type(store).__name__}://{prefix}*",
            fetched_at=datetime.now(UTC),
        )
