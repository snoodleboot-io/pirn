"""``PyarrowToDataBatch`` — bridge knot from Tier-2 :class:`PyarrowDataBatch`
back to Tier-1 :class:`DataBatch`.

Materialises every row as a dict — only do this at the boundary where
downstream knots actually need the dict-based contract (a Tier-1 sink, a
small validator, or a debug step). For larger tables, prefer routing the
:class:`PyarrowDataBatch` directly into a Tier-2 sink.

Algorithm:
    1. Materialise the PyArrow table to a list of row dicts via
       ``table.to_pylist()``.
    2. Return a :class:`DataBatch` wrapping those row dicts, with
       ``source_uri`` and ``fetched_at`` copied from the input batch.

    ```text
    rows = tuple(batch.table.to_pylist())
    return DataBatch(rows=rows, source_uri=batch.source_uri, fetched_at=batch.fetched_at)
    ```

References:
    [1] Apache Arrow Python — pyarrow.Table.to_pylist:
        https://arrow.apache.org/docs/python/generated/pyarrow.Table.html#pyarrow.Table.to_pylist
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.required_engine import RequiredEngine

from pirn_data.data_batch import DataBatch
from pirn_data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowToDataBatch(Knot):
    """Materialise a :class:`PyarrowDataBatch` back into a Tier-1 :class:`DataBatch`."""

    _required_engines: ClassVar[Sequence[RequiredEngine]] = (
        RequiredEngine("pyarrow", extra="data", package="pirn-data"),
    )

    def __init__(
        self,
        *,
        batch: Knot,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(self, batch: PyarrowDataBatch, **_: Any) -> DataBatch:
        """Materialise the PyArrow table to row dicts and return a Tier-1 DataBatch.

        Args:
            batch: The upstream PyarrowDataBatch to materialise.

        Returns:
            A Tier-1 DataBatch of row dicts with the same provenance metadata.
        """
        rows = tuple(batch.table.to_pylist())
        return DataBatch(
            rows=rows,
            source_uri=batch.source_uri,
            fetched_at=batch.fetched_at,
        )
