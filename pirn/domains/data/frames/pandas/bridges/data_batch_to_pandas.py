"""``DataBatchToPandas`` — bridge knot from Tier-1 :class:`DataBatch` to
Tier-2 :class:`PandasDataBatch`.

Constructs a Pandas frame from the row dicts. ``source_uri`` and
``fetched_at`` are propagated unchanged. Used at the seam where a small
upstream batch (fixture, glue) feeds into a tier-2 transform chain.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pandas.pandas_data_batch import PandasDataBatch


class DataBatchToPandas(Knot):
    """Construct a :class:`PandasDataBatch` from a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DataBatch, **_: Any) -> PandasDataBatch:
        if not batch.rows:
            frame = pd.DataFrame()
        else:
            frame = pd.DataFrame(list(batch.rows))
        return PandasDataBatch(
            frame=frame,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
