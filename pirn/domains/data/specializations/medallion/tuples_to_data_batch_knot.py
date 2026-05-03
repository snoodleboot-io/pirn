"""``TuplesToDataBatchKnot`` — convert ``DatabaseQuerySource``'s tuple
output into a Tier-1 :class:`DataBatch` keyed by caller-supplied column
names. Used inside silver/gold medallion knots.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch


class TuplesToDataBatchKnot(Knot):
    """Map a list of row tuples to a :class:`DataBatch`."""

    def __init__(
        self,
        *,
        rows: Knot,
        column_names: Sequence[str],
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        column_tuple = tuple(column_names)
        if not column_tuple:
            raise ValueError(
                "TuplesToDataBatchKnot: column_names must be non-empty"
            )
        self._column_names = column_tuple
        super().__init__(rows=rows, _config=_config, **kwargs)

    async def process(
        self, rows: Iterable[Iterable[Any]], **_: Any
    ) -> DataBatch:
        """Zip row tuples with the configured column names and return a DataBatch of row dicts.

        Args:
            rows: The upstream row tuples to key by the configured column names.

        Returns:
            A DataBatch with each row represented as a dict keyed by column name.
        """
        materialised = tuple(
            dict(zip(self._column_names, tuple(row)))
            for row in rows
        )
        return DataBatch(rows=materialised)
