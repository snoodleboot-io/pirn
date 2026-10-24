"""``RecalledLineageRecord`` — fetch one lineage row's recorded value, or nothing.

One knot per lineage row, so every ``DataStore`` read has its own ``Result``,
retry, timeout and lineage row rather than being one turn of a Python loop the
run cannot see — the shape
:class:`~pirn_agents.memory.patterns.stored_semantic_fact.StoredSemanticFact`
uses for writes, read backwards (Rule 11; PIR-874).

A miss is a value, not a failure: recall tolerates gaps (the value was scrubbed,
evicted, is not a ``MemoryRecord``, or does not match the caller's tags), so
this knot returns ``None`` for them and stays ``Ok``. ``Skipped`` would be the
more expressive outcome but propagates: the engine skips a child whose parent
skipped, so one evicted value would skip the aggregator collecting every other
record.

Internal API. See ``memory_lineage_recall.py``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.memory.management.memory_record import MemoryRecord


class RecalledLineageRecord(Knot):
    """Read the value one lineage row recorded, keeping it only if recall wants it."""

    def __init__(
        self,
        *,
        data_store: Knot | Any,
        output_hash: Knot | str,
        tag_filter: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            data_store=data_store,
            output_hash=output_hash,
            tag_filter=tag_filter,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        data_store: Any,
        output_hash: str,
        tag_filter: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> MemoryRecord | None:
        """Return the ``MemoryRecord`` stored under ``output_hash``, or ``None``.

        ``data_store`` is typed ``Any`` rather than ``DataStore`` for the reason
        ``MemoryLineageRecall.process`` documents: no core backend type mixes in
        ``PirnOpaqueValue``, so declaring the real type makes every knot
        construction raise ``PydanticSchemaGenerationError``. The caller has
        already validated it.

        Args:
            data_store: The ``DataStore`` the writer knot's outputs were
                content-addressed into.
            output_hash: The content hash the lineage row recorded.
            tag_filter: Optional mapping the record's ``tags`` must be a
                superset of. ``None`` keeps every record.

        Returns:
            The record, or ``None`` when the value is gone, is not a
            ``MemoryRecord``, or does not match ``tag_filter``.
        """
        try:
            value = await data_store.get(output_hash)
        except KeyError:
            return None
        if not isinstance(value, MemoryRecord):
            return None
        if tag_filter is not None and not RecalledLineageRecord.matches(value, tag_filter):
            return None
        return value

    @staticmethod
    def matches(record: MemoryRecord, tag_filter: Mapping[str, Any]) -> bool:
        """True if every ``tag_filter`` entry is present and equal in ``record.tags``."""
        return all(
            record.data.tags.get(key, object()) == value for key, value in tag_filter.items()
        )
