"""``TuplesToDataBatchKnot`` — convert a list of row tuples into a Tier-1
:class:`DataBatch` keyed by caller-supplied column names.

Used inside silver/gold medallion knots to bridge from
``DatabaseQuerySource``'s positional-tuple output to dict-keyed
transform knots.

Algorithm:
    1. Receive ``rows`` and ``column_names`` in ``process()``.
    2. Validate that ``column_names`` is non-empty.
    3. Zip each row tuple with the column names to produce a dict.
    4. Return a :class:`DataBatch` wrapping the sequence of row dicts.

References:
    [1] pirn — DataBatch:
        pirn/domains/data/data_batch.py
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class TuplesToDataBatchKnot(Knot):
    """Map a list of row tuples to a :class:`DataBatch`."""

    def __init__(
        self,
        *,
        rows: Knot,
        column_names: Knot | Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(rows=rows, column_names=column_names, _config=_config, **kwargs)

    async def process(
        self,
        *,
        rows: Any,
        column_names: Any,
        **_: Any,
    ) -> DataBatch:
        """Validate column_names, zip rows with column names, return DataBatch.

        Args:
            rows: Upstream row tuples to key by column name.
            column_names: Sequence of column names that correspond to each tuple position.

        Returns:
            A :class:`DataBatch` with each row represented as a dict keyed by column name.

        Raises:
            ValueError: If ``column_names`` is empty.
        """
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError("TuplesToDataBatchKnot: column_names must be non-empty")
        materialised = tuple(dict(zip(column_tuple, tuple(row), strict=False)) for row in rows)
        return DataBatch(rows=materialised)
