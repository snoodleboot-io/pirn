"""``DataBatchToPyarrow`` — bridge knot from Tier-1 :class:`DataBatch` to
Tier-2 :class:`PyarrowDataBatch`.

Constructs a PyArrow table from the row dicts. ``source_uri`` and
``fetched_at`` are propagated unchanged. Used at the seam where a small
upstream batch (fixture, glue) feeds into a Tier-2 transform chain.
"""

from __future__ import annotations

from typing import Any

import pyarrow as pa

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class DataBatchToPyarrow(Knot):
    """Construct a :class:`PyarrowDataBatch` from a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: DataBatch, **_: Any) -> PyarrowDataBatch:
        """Convert a Tier-1 DataBatch of row dicts into a PyarrowDataBatch.

        Args:
            batch: The upstream Tier-1 DataBatch to convert.

        Returns:
            A PyarrowDataBatch wrapping a PyArrow table built from the row dicts.
        """
        if not batch.rows:
            # PyArrow has no concept of a 0-column "empty table" beyond a
            # zero-row table with a schema; without column hints we hand
            # back an explicitly empty table with no columns.
            table = pa.table({})
        else:
            table = pa.Table.from_pylist(list(batch.rows))
        return PyarrowDataBatch(
            table=table,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
