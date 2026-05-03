"""``DataBatchToTuplesKnot`` — collapse a Tier-1 :class:`DataBatch` back
into a list of tuples keyed by caller-supplied column order. Used by
silver/gold medallion knots before handing to a positional-bind INSERT
sink.
"""

from __future__ import annotations

from typing import Any, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class DataBatchToTuplesKnot(Knot):
    """Map a :class:`DataBatch` to a list of column-ordered tuples."""

    def __init__(
        self,
        *,
        batch: Knot,
        column_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError(
                "DataBatchToTuplesKnot: column_names must be non-empty"
            )
        self._column_names = column_tuple
        super().__init__(batch=batch, _config=_config, **kwargs)

    async def process(
        self, batch: DataBatch, **_: Any
    ) -> list[tuple[Any, ...]]:
        """Project each DataBatch row to a column-ordered tuple and return the list.

        Args:
            batch: The DataBatch whose rows will be projected to positional tuples.

        Returns:
            A list of tuples, one per row, with values ordered by the configured column names.
        """
        return [
            tuple(row.get(column) for column in self._column_names)
            for row in batch.rows
        ]
