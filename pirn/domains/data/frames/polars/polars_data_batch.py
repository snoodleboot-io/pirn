"""``PolarsDataBatch`` — Tier-2 adapter wrapping a :class:`polars.DataFrame`.

Mirrors the metadata shape of :class:`pirn.domains.data.data_batch.DataBatch`
(``source_uri``, ``fetched_at``) but holds a real Polars frame so transform
knots can dispatch to native Polars expressions instead of iterating over a
``tuple[dict, ...]``.

Polars is the first Tier-2 engine; see ARD: *Decision: Tiered Data-Domain
Architecture (Position B)* for why Tier-2 transforms are not unified
behind a generic ``Frame`` interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import polars as pl
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class PolarsDataBatch:
    """A Polars DataFrame plus its provenance metadata.

    Attributes
    ----------
    frame:
        The underlying ``polars.DataFrame``. Replace via :meth:`with_frame`
        to keep instances immutable.
    source_uri:
        Where the data came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the frame was materialised.
    """

    frame: pl.DataFrame
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def row_count(self) -> int:
        return self.frame.height

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.frame.columns)

    def with_frame(self, frame: pl.DataFrame) -> "PolarsDataBatch":
        """Return a copy with ``frame`` replaced; metadata preserved."""
        return PolarsDataBatch(
            frame=frame,
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
        dataclass fields and chokes on :class:`polars.DataFrame`, which
        is not pydantic-compatible. Override here so pydantic just
        checks ``isinstance(value, PolarsDataBatch)`` and leaves the
        wrapped frame alone.
        """
        return core_schema.is_instance_schema(cls)
