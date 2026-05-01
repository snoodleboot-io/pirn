"""``PyarrowToDataBatch`` — bridge knot from Tier-2 :class:`PyarrowDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises every row as a dict — only do this at the boundary where
downstream knots actually need the dict-based contract (a Tier-1 sink, a
small validator, or a debug step). For larger tables, prefer routing the
:class:`PyarrowDataBatch` directly into a Tier-2 sink.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowToDataBatch(Knot):
    """Materialise a :class:`PyarrowDataBatch` back into a Tier-1 :class:`DataBatch`."""

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: PyarrowDataBatch, **_: Any) -> DataBatch:
        rows = tuple(batch.table.to_pylist())
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
