"""``DataBatchToDatafusion`` — bridge Knot from Tier-1 :class:`DataBatch`
to Tier-2 :class:`DatafusionDataBatch`.

Materialises the rows into a logical DataFrame on the supplied
:class:`~pirn.domains.data.frames.datafusion.datafusion_session_context_knot.DatafusionSessionContextKnot`'s
context. ``source_uri`` and ``fetched_at`` are propagated unchanged.

Used at the seam where a small upstream batch (fixture, glue) feeds
into a Tier-2 transform chain that expects a SQL engine.

Algorithm:
    1. Receive the resolved :class:`DataBatch` and :class:`datafusion.SessionContext`.
    2. If the batch is empty, synthesise a zero-row placeholder DataFrame
       (DataFusion has no shape-aware empty-frame constructor).
    3. Otherwise, register the rows via ``context.from_pylist()``.
    4. Wrap the resulting DataFrame in a :class:`DatafusionDataBatch`.

References:
    [1] Apache DataFusion Python — SessionContext.from_pylist:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.SessionContext.from_pylist
"""

from __future__ import annotations

from typing import Any

import datafusion as df  # used in _build_frame return type

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)
from pirn.domains.data.frames.datafusion.datafusion_session_context import (
    DatafusionSessionContext,
)
from pirn.domains.data.frames.datafusion.datafusion_session_context_knot import (
    DatafusionSessionContextKnot,
)


class DataBatchToDatafusion(Knot):
    """Construct a :class:`DatafusionDataBatch` from a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        context: DatafusionSessionContextKnot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, context=context, _config=_config, **kwargs)

    async def process(
        self,
        batch: DataBatch,
        context: DatafusionSessionContext,
        **_: Any,
    ) -> DatafusionDataBatch:
        """Convert a Tier-1 DataBatch into a DatafusionDataBatch.

        Args:
            batch: The Tier-1 DataBatch whose rows are loaded into DataFusion.
            context: The resolved DataFusion session context wrapper.

        Returns:
            A DatafusionDataBatch wrapping a DataFusion DataFrame with the batch's rows.
        """
        frame = self._build_frame(context.ctx, batch)
        return DatafusionDataBatch(
            frame=frame,
            context=context.ctx,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )

    @staticmethod
    def _build_frame(context: df.SessionContext, batch: DataBatch) -> df.DataFrame:
        if not batch.rows:
            # DataFusion has no native "empty DataFrame" constructor that
            # matches the user's column shape, so synthesise a zero-row frame.
            return context.sql("SELECT NULL AS _empty WHERE FALSE")
        return context.from_pylist(list(batch.rows))
