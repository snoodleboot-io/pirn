"""``LakehouseTableSink`` — write a :class:`DataBatch` to a
:class:`LakehouseTable`.

Three modes via the ``mode`` parameter:

* ``"append"`` — insert as a new commit (default).
* ``"overwrite"`` — replace the table or a partition slice.
* ``"merge"`` — upsert by the ``merge_on`` keys.

Algorithm:
    1. Receive resolved inputs in ``process()``: ``batch``, ``table``,
       ``mode``, ``merge_on``, and ``partition_filter``.
    2. Validate: ``table`` must be a :class:`LakehouseTable`;
       ``mode`` must be one of ``("append", "overwrite", "merge")``;
       ``mode="merge"`` requires a non-empty ``merge_on`` sequence.
    3. Wrap ``batch.rows`` in an async generator of row dicts.
    4. Dispatch to ``table.append``, ``table.overwrite``, or
       ``table.merge`` according to ``mode``.
    5. Return the snapshot-id string produced by the table operation.

References:
    [1] pirn — LakehouseTable interface:
        pirn/domains/data/lakehouse/lakehouse_table.py
    [2] pirn — FileSink (analogous object-store sink pattern):
        pirn/domains/data/sinks/file_sink.py
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Any

from typing import ClassVar

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.domains.data.data_batch import DataBatch
from pirn.domains.data.lakehouse.lakehouse_table import LakehouseTable
from pirn.nodes.sink import Sink


class LakehouseTableSink(Sink):
    """Write a :class:`DataBatch` to a lakehouse table; return the new
    snapshot id."""

    _allowed_modes: ClassVar[tuple[str, ...]] = ("append", "overwrite", "merge")

    def __init__(
        self,
        *,
        batch: Knot,
        table: Knot | LakehouseTable,
        mode: Knot | str = "append",
        merge_on: Knot | Sequence[str] | None = None,
        partition_filter: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            batch=batch,
            table=table,
            mode=mode,
            merge_on=merge_on,
            partition_filter=partition_filter,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        *,
        batch: DataBatch,
        table: Any,
        mode: Any = "append",
        merge_on: Any = None,
        partition_filter: Any = None,
        **_: Any,
    ) -> str:
        if not isinstance(table, LakehouseTable):
            raise TypeError("LakehouseTableSink: table must be a LakehouseTable instance")
        if mode not in self._allowed_modes:
            raise ValueError(
                f"LakehouseTableSink: mode must be one of {list(self._allowed_modes)}, got {mode!r}"
            )
        if mode == "merge" and not (merge_on and list(merge_on)):
            raise ValueError("LakehouseTableSink: mode='merge' requires non-empty merge_on")

        async def _records() -> AsyncIterator[Mapping[str, Any]]:
            for row in batch.rows:
                yield row

        if mode == "append":
            return await table.append(_records())
        if mode == "overwrite":
            return await table.overwrite(_records(), partition_filter=partition_filter)
        return await table.merge(_records(), on=merge_on)
