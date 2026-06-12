"""``PyarrowDataBatch`` — Tier-2 adapter wrapping a :class:`pyarrow.Table`.

Mirrors the metadata shape of :class:`pirn.domains.data.data_batch.DataBatch`
(``source_uri``, ``fetched_at``) but holds a real PyArrow table so transform
knots can dispatch to ``pyarrow.compute`` kernels instead of iterating over
a ``tuple[dict, ...]``.

PyArrow tables are the columnar lingua franca for the Tier-2 ecosystem —
Polars, Pandas, DuckDB, and DataFusion can all interchange via Arrow, so
``PyarrowDataBatch`` is also the natural intermediate format for cross-
engine bridges.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pyarrow as pa
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class PyarrowDataBatch:
    """A PyArrow Table plus its provenance metadata.

    Attributes
    ----------
    table:
        The underlying ``pyarrow.Table``. Replace via :meth:`with_table`
        to keep instances immutable.
    source_uri:
        Where the data came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the table was materialised.
    """

    table: pa.Table
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def row_count(self) -> int:
        return int(self.table.num_rows)

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.table.column_names)

    def with_table(self, table: pa.Table) -> PyarrowDataBatch:
        """Return a copy with ``table`` replaced; metadata preserved."""
        return PyarrowDataBatch(
            table=table,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque.

        Pirn's IO validation uses pydantic to check values flowing
        between knots. The default schema generator descends into
        dataclass fields and chokes on :class:`pyarrow.Table`, which
        is not pydantic-compatible. Override here so pydantic just
        checks ``isinstance(value, PyarrowDataBatch)`` and leaves the
        wrapped table alone.
        """
        return core_schema.is_instance_schema(cls)
