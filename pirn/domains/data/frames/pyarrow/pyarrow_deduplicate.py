"""``PyarrowDeduplicate`` — Tier-2 dedup keeping the first occurrence per
key tuple.

PyArrow's relational toolkit does not expose a direct
"distinct-by-subset" operation on tables (only a global ``unique``
aggregation on a single array). To preserve first-occurrence semantics
we:

1. Stamp every input row with its position in a fresh ``_pirn_idx``
   column.
2. Group by the key columns and aggregate ``_pirn_idx`` with ``min`` —
   that's the index of the first row in each group.
3. Sort the resulting indices ascending so output order matches input
   order, then ``table.take(indices)``.

This mirrors the Tier-1 :class:`Deduplicate` semantics. Group-by and
``take`` are both vectorised C++ kernels in PyArrow.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.frames.pyarrow.pyarrow_data_batch import PyarrowDataBatch


class PyarrowDeduplicate(Knot):
    """Drop duplicate rows by key tuple, keeping the first occurrence."""

    def __init__(
        self,
        *,
        batch: Knot,
        keys: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, keys=keys, _config=_config, **kwargs)

    async def process(
        self,
        batch: PyarrowDataBatch,
        keys: Any,  # Sequence[str] — deferred; str/empty checks fire in process(), not pydantic
        **_: Any,
    ) -> PyarrowDataBatch:
        """Remove duplicate rows by key, keeping the first occurrence.

        Args:
            batch: The upstream PyarrowDataBatch to deduplicate.
            keys: Column names that form the deduplication key.

        Returns:
            A new PyarrowDataBatch with duplicate key-tuple rows removed,
            preserving input order.
        """
        if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
            raise TypeError(
                "PyarrowDeduplicate: keys must be a sequence of column names"
            )
        if not keys:
            raise ValueError("PyarrowDeduplicate: keys must be non-empty")
        for key in keys:
            if not isinstance(key, str) or not key:
                raise TypeError(
                    "PyarrowDeduplicate: every entry in keys must be a non-empty string"
                )

        table = batch.table
        if table.num_rows == 0:
            return batch
        # Stamp each row with its input position. Use a column name
        # unlikely to clash with user data.
        idx_name = "_pirn_idx"
        # Defensive: bump the suffix until the name is free.
        while idx_name in table.column_names:
            idx_name = idx_name + "_"
        index_array = pa.array(range(table.num_rows), type=pa.int64())
        stamped = table.append_column(idx_name, index_array)
        # Per-group minimum index = the first occurrence in input order.
        grouped = stamped.group_by(list(keys)).aggregate(
            [(idx_name, "min")]
        )
        # The aggregate output column is named ``"<idx_name>_min"`` per
        # PyArrow's convention.
        first_indices = grouped.column(f"{idx_name}_min")
        # Sort ascending so output order == input order of first occurrences.
        sort_indices = pc.sort_indices(first_indices)
        ordered_indices = pc.take(first_indices, sort_indices)
        return batch.with_table(table.take(ordered_indices))
