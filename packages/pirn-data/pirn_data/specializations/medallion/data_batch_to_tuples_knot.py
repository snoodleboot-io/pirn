"""``DataBatchToTuplesKnot`` — collapse a Tier-1 :class:`DataBatch` back
into a list of tuples keyed by caller-supplied column order.

Used by silver/gold medallion knots before handing off to a
positional-bind INSERT sink.  Both ``batch`` and ``column_names`` arrive
as resolved values in ``process()``.

Algorithm:
    1. Receive ``batch`` and ``column_names`` in ``process()``.
    2. Validate that ``column_names`` is non-empty.
    3. For each row dict in ``batch.rows``, project values in the order
       of ``column_names``, substituting ``None`` for missing keys.
    4. Return the list of projected tuples.

References:
    [1] pirn — DataBatch:
        pirn_data/data_batch.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.disassembler import Disassembler
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_data.value_shape import ValueShape


class DataBatchToTuplesKnot(Disassembler):
    """Map a :class:`DataBatch` to a list of column-ordered tuples."""

    def __init__(
        self,
        *,
        batch: Knot,
        column_names: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(batch=batch, column_names=column_names, _config=_config, **kwargs)

    async def process(
        self,
        *,
        batch: Any,
        column_names: Any,
        **_: Any,
    ) -> list[tuple[Any, ...]]:
        """Validate column_names, project each DataBatch row to a tuple, return the list.

        Args:
            batch: The :class:`DataBatch` whose rows will be projected.
            column_names: Ordered column names determining the tuple value order.

        Returns:
            A list of tuples, one per row, with values ordered by ``column_names``.

        Raises:
            TypeError: If ``column_names`` is not a sequence of strings.
            ValueError: If ``column_names`` is empty.
        """
        if not ValueShape.is_sequence(column_names) or isinstance(column_names, (str, bytes)):
            raise TypeError("DataBatchToTuplesKnot: column_names must be a sequence of strings")
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError("DataBatchToTuplesKnot: column_names must be non-empty")
        return [tuple(row.get(column) for column in column_tuple) for row in batch.rows]
