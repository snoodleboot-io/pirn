"""``LakehouseTableSink`` — write a :class:`DataBatch` to a
:class:`LakehouseTable`.

Three modes via the ``mode`` parameter:

* ``"append"`` — insert as a new commit (default).
* ``"overwrite"`` — replace the table or a partition slice.
* ``"merge"`` — upsert by the ``merge_on`` keys.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, ClassVar, Mapping, Sequence

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable


class LakehouseTableSink(Knot):
    """Write a :class:`DataBatch` to a lakehouse table; return the new
    snapshot id."""

    _allowed_modes: ClassVar[tuple[str, ...]] = ("append", "overwrite", "merge")

    def __init__(
        self,
        *,
        batch: Knot,
        table: LakehouseTable,
        mode: str = "append",
        merge_on: Sequence[str] | None = None,
        partition_filter: Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        if not isinstance(table, LakehouseTable):
            raise TypeError(
                "LakehouseTableSink: table must be a LakehouseTable instance"
            )
        if mode not in self._allowed_modes:
            raise ValueError(
                f"LakehouseTableSink: mode must be one of "
                f"{list(self._allowed_modes)}, got {mode!r}"
            )
        if mode == "merge":
            if merge_on is None or not list(merge_on):
                raise ValueError(
                    "LakehouseTableSink: mode='merge' requires non-empty merge_on"
                )
        self._table = table
        self._mode = mode
        self._merge_on = tuple(merge_on) if merge_on is not None else None
        self._partition_filter = (
            dict(partition_filter) if partition_filter is not None else None
        )
        super().__init__(batch=batch, _config=_config, **kwargs)

    @property
    def mode(self) -> str:
        return self._mode

    async def process(self, batch: DataBatch, **_: Any) -> str:
        """Write the DataBatch to the lakehouse table using the configured mode and return the snapshot id.

        Args:
            batch: The DataBatch of rows to persist.

        Returns:
            The snapshot id string produced by the lakehouse write operation.
        """
        async def _records() -> AsyncIterator[Mapping[str, Any]]:
            for row in batch.rows:
                yield row

        if self._mode == "append":
            return await self._table.append(_records())
        if self._mode == "overwrite":
            return await self._table.overwrite(
                _records(), partition_filter=self._partition_filter
            )
        # merge
        assert self._merge_on is not None
        return await self._table.merge(_records(), on=self._merge_on)
