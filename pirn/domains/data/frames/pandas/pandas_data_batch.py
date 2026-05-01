"""``PandasDataBatch`` — Tier-2 adapter wrapping a :class:`pandas.DataFrame`.

Mirrors the metadata shape of :class:`pirn.domains.data.data_batch.DataBatch`
(``source_uri``, ``fetched_at``) but holds a real Pandas frame so transform
knots can dispatch to native Pandas APIs instead of iterating over a
``tuple[dict, ...]``.

Pandas is a Tier-2 engine alongside Polars; see ARD: *Decision: Tiered
Data-Domain Architecture (Position B)* for why Tier-2 transforms are not
unified behind a generic ``Frame`` interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import pandas as pd
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class PandasDataBatch:
    """A Pandas DataFrame plus its provenance metadata.

    Attributes
    ----------
    frame:
        The underlying ``pandas.DataFrame``. Replace via :meth:`with_frame`
        to keep instances immutable.
    source_uri:
        Where the data came from (DSN, file path, API endpoint). DSN-style
        values must be passed through
        :class:`pirn.domains.connectors.dsn_scrubber.DsnScrubber` before
        assignment.
    fetched_at:
        UTC instant the frame was materialised.
    """

    frame: pd.DataFrame
    source_uri: str = ""
    fetched_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def row_count(self) -> int:
        return int(self.frame.shape[0])

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.frame.columns)

    def with_frame(self, frame: pd.DataFrame) -> "PandasDataBatch":
        """Return a copy with ``frame`` replaced; metadata preserved."""
        return PandasDataBatch(
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
        dataclass fields and chokes on :class:`pandas.DataFrame`, which
        is not pydantic-compatible. Override here so pydantic just
        checks ``isinstance(value, PandasDataBatch)`` and leaves the
        wrapped frame alone.
        """
        return core_schema.is_instance_schema(cls)
