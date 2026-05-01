"""A batch of rows flowing through the data pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping

from pirn.domains.data.data_schema import DataSchema


@dataclass(frozen=True)
class DataBatch:
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
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber` before
        assignment to avoid leaking credentials into lineage records.
    fetched_at:
        UTC instant the data was materialised.
    """

    rows: tuple[Mapping[str, Any], ...] = ()
    schema: DataSchema = field(default_factory=DataSchema)
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def with_rows(self, rows: tuple[Mapping[str, Any], ...]) -> "DataBatch":
        """Copy with ``rows`` replaced; schema/uri/fetched_at preserved."""
        return DataBatch(
            rows=rows,
            schema=self.schema,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    def with_schema(self, schema: DataSchema) -> "DataBatch":
        """Copy with ``schema`` replaced; rows preserved."""
        return DataBatch(
            rows=self.rows,
            schema=schema,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )
