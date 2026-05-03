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


class DirectorySource(Knot):
    """Glob a prefix; emit one :class:`DataBatch` per file (or one
    concatenated batch when ``concatenate=True``)."""

    def __init__(
        self,
        *,
        store: ObjectStore,
        format: FileFormat,
        prefix: str,
        concatenate: bool = False,
        schema: DataSchema | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(store, ObjectStore):
            raise TypeError(
                "DirectorySource: store must be an ObjectStore instance"
            )
        if not isinstance(format, FileFormat):
            raise TypeError(
                "DirectorySource: format must be a FileFormat instance"
            )
        if not isinstance(prefix, str):
            raise TypeError(
                "DirectorySource: prefix must be a string (use '' for root)"
            )
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError(
                "DirectorySource: schema must be a DataSchema instance"
            )
        self._store = store
        self._format = format
        self._prefix = prefix
        self._concatenate = concatenate
        self._schema = schema
        super().__init__(_config=_config, **kwargs)

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def concatenate(self) -> bool:
        return self._concatenate

    async def process(
        self, **_: Any
    ) -> tuple[DataBatch, ...] | DataBatch:
        """List, decode, and return all files under the configured prefix as per-file batches or one concatenated batch.

        Returns:
            A tuple of per-file DataBatches, or a single concatenated DataBatch when
            concatenate is True.
        """
        keys: list[str] = []
        key_iter = await self._store.list(self._prefix)
        async for k in key_iter:
            keys.append(k)
        keys.sort()

        per_file_batches: list[DataBatch] = []
        for k in keys:
            body = await self._store.get(k)
            records = await self._format.read(body)
            rows: list[dict[str, Any]] = []
            async for record in records:
                rows.append(dict(record))
            per_file_batches.append(
                DataBatch(
                    rows=tuple(rows),
                    schema=(
                        self._schema if self._schema is not None
                        else DataSchema()
                    ),
                    source_uri=f"{type(self._store).__name__}://{k}",
                    fetched_at=datetime.now(timezone.utc),
                )
            )

        if not self._concatenate:
            return tuple(per_file_batches)

        all_rows: list[Mapping[str, Any]] = []
        for batch in per_file_batches:
            all_rows.extend(batch.rows)
        return DataBatch(
            rows=tuple(all_rows),
            schema=(
                self._schema if self._schema is not None
                else DataSchema()
            ),
            source_uri=f"{type(self._store).__name__}://{self._prefix}*",
            fetched_at=datetime.now(timezone.utc),
        )
