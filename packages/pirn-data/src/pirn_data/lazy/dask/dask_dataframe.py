"""``DaskDataFrame`` — Tier-3 adapter wrapping a ``dask.dataframe.DataFrame``.

Just like :class:`pirn_data.lazy.ibis.ibis_table.IbisTable`, this
adapter holds a *deferred* computation. A ``dask.dataframe.DataFrame``
is a lazy task graph over partitioned pandas frames — no rows are
materialised until ``.compute()`` is called. Tier-3 knots transform the
graph; only the terminal sink (:class:`DaskCompute`) calls
``.compute()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import dask.dataframe as dd
from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema


@dataclass(frozen=True)
class DaskDataFrame:
    """A ``dask.dataframe.DataFrame`` plus its provenance metadata.

    Attributes
    ----------
    frame:
        The deferred ``dask.dataframe.DataFrame``. Pirn does not call
        ``.compute()`` on this object — that's the sink's job.
    backend_name:
        Human-readable backend identifier (e.g. ``"dask"``).
    source_uri:
        Optional path/URI hint for lineage. DSN-style values must be
        scrubbed before assignment.
    fetched_at:
        UTC instant the frame was constructed.
    """

    frame: dd.DataFrame
    backend_name: str = "dask"
    source_uri: str = ""
    fetched_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(self.frame.columns)

    @property
    def npartitions(self) -> int:
        return int(self.frame.npartitions)

    def with_frame(self, frame: dd.DataFrame) -> DaskDataFrame:
        """Return a copy with ``frame`` replaced; metadata preserved."""
        return DaskDataFrame(
            frame=frame,
            backend_name=self.backend_name,
            source_uri=self.source_uri,
            fetched_at=self.fetched_at,
        )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: Any, handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        """Tell pydantic to treat this batch as opaque."""
        return core_schema.is_instance_schema(cls)
