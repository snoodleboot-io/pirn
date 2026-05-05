"""``PolarsToDataBatch`` — bridge knot from Tier-2 :class:`PolarsDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises every row as a dict — only do this at the boundary where
downstream knots actually need the dict-based contract (a Tier-1 sink, a
small validator, or a debug step). For larger frames, prefer routing the
:class:`PolarsDataBatch` directly into a Tier-2 sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.polars.polars_data_batch import PolarsDataBatch


class PolarsToDataBatch(Knot):
    """Materialise a :class:`PolarsDataBatch` back into a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: PolarsDataBatch, **_: Any) -> DataBatch:
        """Materialise the Polars DataFrame to row dicts and return a Tier-1 DataBatch.

        Args:
            batch: The PolarsDataBatch whose DataFrame is materialised to row dicts.

        Returns:
            A Tier-1 DataBatch with materialised rows, source_uri, and fetched_at preserved.
        """
        rows = tuple(batch.frame.to_dicts())
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
