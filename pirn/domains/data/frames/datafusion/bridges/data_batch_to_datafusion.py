"""``DataBatchToDatafusion`` — bridge knot from Tier-1 :class:`DataBatch`
to Tier-2 :class:`DatafusionDataBatch`.

Constructs a fresh :class:`datafusion.SessionContext` (unless one is
supplied) and materialises the rows into a logical DataFrame on that
context. ``source_uri`` and ``fetched_at`` are propagated unchanged.

Used at the seam where a small upstream batch (fixture, glue) feeds
into a Tier-2 transform chain that expects a SQL engine.
"""

from __future__ import annotations

from typing import Any

import datafusion as df

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class DataBatchToDatafusion(Knot):
    """Construct a :class:`DatafusionDataBatch` from a Tier-1 :class:`DataBatch`.

    A caller may inject a pre-existing ``context`` so several bridges
    share a single in-process DataFusion engine. Otherwise a fresh
    :class:`datafusion.SessionContext` is opened per knot invocation.
    """

    def __init__(
        self,
        *,
        batch: Knot,
        context: df.SessionContext | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        # Capture the SessionContext as instance state *before* calling
        # super().__init__ so the framework's content-addressing
        # serialiser doesn't try to pickle the (unpicklable) Rust
        # context.
        self._context = context
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DataBatch, **_: Any) -> DatafusionDataBatch:
        """Convert a Tier-1 DataBatch into a DatafusionDataBatch by registering rows with the session context.

        Args:
            batch: The Tier-1 DataBatch whose rows are loaded into DataFusion.

        Returns:
            A DatafusionDataBatch wrapping a DataFusion DataFrame with the batch's rows.
        """
        context = self._context
        if context is None:
            context = df.SessionContext()
        frame = self._build_frame(context, batch)
        return DatafusionDataBatch(
            frame=frame,
            context=context,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )

    def _build_frame(
        self, context: df.SessionContext, batch: DataBatch
    ) -> df.DataFrame:
        if not batch.rows:
            # DataFusion has no native "empty DataFrame" constructor that
            # matches the user's column shape (since we don't know it),
            # so we synthesise a zero-row frame with a single placeholder
            # column. Downstream knots that need the real column shape
            # should not be wired up to an empty Tier-1 input.
            return context.sql("SELECT NULL AS _empty WHERE FALSE")
        return context.from_pylist(list(batch.rows))
