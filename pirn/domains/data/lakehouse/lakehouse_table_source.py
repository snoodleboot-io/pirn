"""``LakehouseTableSource`` — read from a :class:`LakehouseTable` into
a :class:`DataBatch`.

Mirrors the shape of :class:`FileSource` but takes a
:class:`LakehouseTable` instead of an ``ObjectStore × FileFormat``
pair, because lakehouse tables are NOT file formats — they have
transaction logs and time-travel semantics.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.data_schema import DataSchema
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class LakehouseTableSource(Knot):
    """Scan a lakehouse table; emit a :class:`DataBatch`.

    Pass ``snapshot_id`` or ``as_of_timestamp`` for time-travel reads.
    Pass ``filter`` and ``columns`` for predicate push-down and column
    projection.
    """

    def __init__(
        self,
        *,
        table: LakehouseTable,
        snapshot_id: int | str | None = None,
        as_of_timestamp: datetime | None = None,
        filter: Mapping[str, Any] | None = None,
        columns: Sequence[str] | None = None,
        schema: DataSchema | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(table, LakehouseTable):
            raise TypeError(
                "LakehouseTableSource: table must be a LakehouseTable instance"
            )
        if snapshot_id is not None and as_of_timestamp is not None:
            raise ValueError(
                "LakehouseTableSource: snapshot_id and as_of_timestamp "
                "are mutually exclusive"
            )
        if schema is not None and not isinstance(schema, DataSchema):
            raise TypeError(
                "LakehouseTableSource: schema must be a DataSchema instance"
            )
        self._table = table
        self._snapshot_id = snapshot_id
        self._as_of_timestamp = as_of_timestamp
        self._filter = dict(filter) if filter is not None else None
        self._columns = tuple(columns) if columns is not None else None
        self._schema = schema
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> DataBatch:
        """Scan the lakehouse table and return all matching records as a DataBatch.

        Returns:
            A DataBatch containing all rows returned by the lakehouse scan.
        """
        rows: list[dict[str, Any]] = []
        records = await self._table.scan(
            snapshot_id=self._snapshot_id,
            as_of_timestamp=self._as_of_timestamp,
            filter=self._filter,
            columns=self._columns,
        )
        async for record in records:
            rows.append(dict(record))
        return DataBatch(
            rows=tuple(rows),
            schema=(
                self._schema if self._schema is not None else DataSchema()
            ),
            source_uri=f"lakehouse://{self._table.name}",
            fetched_at=datetime.now(timezone.utc),
        )
