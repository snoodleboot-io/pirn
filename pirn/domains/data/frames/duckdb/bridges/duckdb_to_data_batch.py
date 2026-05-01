"""``DuckdbToDataBatch`` — bridge knot from Tier-2 :class:`DuckdbDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises the relation by calling ``relation.fetchall()`` and zipping
each row tuple with the relation's column names to produce row dicts —
only do this at the boundary where downstream knots actually need the
dict-based contract (a Tier-1 sink, a small validator, or a debug step).
For larger relations, prefer routing the :class:`DuckdbDataBatch`
directly into a Tier-2 sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.duckdb.duckdb_data_batch import DuckdbDataBatch


class DuckdbToDataBatch(Knot):
    """Materialise a :class:`DuckdbDataBatch` back into a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DuckdbDataBatch, **_: Any) -> DataBatch:
        columns = tuple(batch.relation.columns)
        fetched = batch.relation.fetchall()
        rows = tuple({columns[i]: value for i, value in enumerate(row)} for row in fetched)
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
