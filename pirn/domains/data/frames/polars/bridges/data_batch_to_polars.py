"""``DataBatchToPolars`` — bridge knot from Tier-1 :class:`DataBatch` to
Tier-2 :class:`PolarsDataBatch`.

Constructs a Polars frame from the row dicts. ``source_uri`` and
``fetched_at`` are propagated unchanged. Used at the seam where a small
upstream batch (fixture, glue) feeds into a tier-2 transform chain.
"""

from __future__ import annotations

from typing import Any

import polars as pl

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class DataBatchToPolars(Knot):
    """Construct a :class:`PolarsDataBatch` from a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DataBatch, **_: Any) -> PolarsDataBatch:
        if not batch.rows:
            frame = pl.DataFrame()
        else:
            frame = pl.DataFrame(list(batch.rows))
        return PolarsDataBatch(
            frame=frame,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
