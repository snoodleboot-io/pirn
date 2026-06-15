"""A batch of rows flowing through the data pipeline."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_data.data_schema import DataSchema


@dataclass(frozen=True)
class DataBatch(PirnOpaqueValue):
    """Tabular batch of rows.

    Each row is a ``dict[str, Any]`` keyed by column name. Heavy frames
    (Pandas / Arrow / Polars) wrap into ``DataBatch`` via thin adapters in
    the sources / transforms modules.

    Attributes
    ----------
    rows:
        Sequence of row dicts.
    schema:
        Schema the rows conform to.
    source_uri:
        Where the rows came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.connectors.dsn_scrubber.DsnScrubber` before
        assignment to avoid leaking credentials into lineage records.
    fetched_at:
        UTC instant the data was materialised.
    """

    rows: tuple[Mapping[str, Any], ...] = ()
    schema: DataSchema = field(default_factory=DataSchema)
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def with_rows(self, rows: tuple[Mapping[str, Any], ...]) -> DataBatch:
        """Copy with ``rows`` replaced; schema/uri/fetched_at preserved."""
        return DataBatch(
            rows=rows,
            schema=self.schema,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    def with_schema(self, schema: DataSchema) -> DataBatch:
        """Copy with ``schema`` replaced; rows preserved."""
        return DataBatch(
            rows=self.rows,
            schema=schema,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    def _pirn_audit_dict(self) -> dict[str, Any]:
        """Flatten to a primitive dict for pydantic serialisation.

        Pirn IO validation only needs ``isinstance(value, DataBatch)``;
        content-addressing flattens the rows into this stable summary.
        The contained :class:`DataSchema` (with its
        ``Mapping[str, type]`` columns) is intentionally omitted —
        ``DataSchema`` is opaque-serialised separately when needed.
        """
        return {
            "row_count": self.row_count,
            "source_uri": self.source_uri,
            "fetched_at": self.fetched_at.isoformat(),
            "rows": [dict(r) for r in self.rows],
        }

    def __pirn_canonical__(self) -> dict[str, Any]:
        """Sanctioned canonical form for :func:`pirn.core.hashing.content_hash`.

        Returned dict is fully JSON-serialisable: ``schema.columns`` is
        flattened to ``{name: type-name}`` so the otherwise-opaque
        :class:`type` values do not blow up the hasher. The audit dict
        deliberately omits the schema (pydantic IO already validates the
        boundary); content-addressing keeps it so two structurally
        identical batches with the same column types hash equally.
        """
        return {
            "row_count": self.row_count,
            "source_uri": self.source_uri,
            "fetched_at": self.fetched_at.isoformat(),
            "rows": [dict(r) for r in self.rows],
            "schema_columns": {
                name: column_type.__name__ for name, column_type in self.schema.columns.items()
            },
        }
