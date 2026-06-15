"""``DatafusionToDataBatch`` — bridge knot from Tier-2
:class:`DatafusionDataBatch` back to Tier-1 :class:`DataBatch`.

Materialises the lazy DataFrame by calling ``to_pylist()`` to produce
row dicts — only do this at the boundary where downstream knots
actually need the dict-based contract (a Tier-1 sink, a small
validator, or a debug step). For larger frames, prefer routing the
:class:`DatafusionDataBatch` directly into a Tier-2 sink.

Algorithm:
    1. Receive a :class:`DatafusionDataBatch` whose ``frame`` is a lazy
       DataFusion ``DataFrame``.
    2. Call ``frame.to_pylist()`` to trigger execution and materialise
       all rows as Python dicts.
    3. Wrap the result in a Tier-1 :class:`DataBatch`, forwarding
       ``source_uri`` and ``fetched_at`` from the input batch so
       provenance metadata is not lost at the tier boundary.

References:
    [1] Apache DataFusion Python — ``DataFrame.to_pylist``:
        https://datafusion.apache.org/python/autoapi/datafusion/index.html#datafusion.DataFrame.to_pylist
    [2] Alternative: ``DataFrame.collect()`` returns Arrow RecordBatches
        (chosen ``to_pylist`` here for direct dict conversion without an
        intermediate PyArrow step).
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.data_batch import DataBatch
from pirn_data.frames.datafusion.datafusion_data_batch import (
    DatafusionDataBatch,
)


class DatafusionToDataBatch(Knot):
    """Materialise a :class:`DatafusionDataBatch` back into a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DatafusionDataBatch, **_: Any) -> DataBatch:
        """Materialise the DataFusion DataFrame to row dicts and return a Tier-1 DataBatch.

        Args:
            batch: The DatafusionDataBatch whose DataFrame is materialised to row dicts.

        Returns:
            A Tier-1 DataBatch with materialised rows, source_uri and fetched_at preserved.
        """
        rows = tuple(batch.frame.to_pylist())
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
