"""``MemoryLineageRecall`` — recall memory records straight from core's lineage.

ADR "agents speaks core" WS3's forward recall path. A writer knot (see
``MemoryWriter``/``EpisodicEpisodeWriter``/the ``memory_patterns/`` writers)
needs no separate keyed write any more: it simply *returns* a
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord` as its
``process()`` output, and the engine content-addresses that value into the
tapestry's ``DataStore`` and records a ``KnotLineage`` row for it — the same
thing it already does for every knot's output (see
``pirn.engine.engine``: ``ContentHasher.hash(result.value)`` /
``data_store.put(out_hash, result.value)``). Recall is the read side of that:
look up every invocation of one writer knot across history, and fetch the
records those invocations produced.

This does not replace :class:`~pirn_agents.memory.memory_retriever.MemoryRetriever`
or ``EpisodicMemoryRetriever`` — those still serve the ``MemoryStore``-backed
path (a vector/graph index, or the ``DataStoreMemoryStore`` key-value adapter), which is the
only place *similarity* search lives. This knot answers a different question:
"every record this writer node has ever produced", independent of any keyed
store at all.

Namespace scoping
------------------
``RunHistory.query_lineage_by_knot_id`` returns every invocation across every
run of that knot id. When the same writer node backs multiple sessions,
``tag_filter`` narrows the result to records whose ``data.tags``
contains the given key/value pairs (e.g. ``{"session_id": "s1"}``) — the free-
form namespace a writer knot already stamps into
:class:`~pirn_agents.memory.management.memory_content.MemoryContent`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.recalled_lineage_record import RecalledLineageRecord


class MemoryLineageRecall(Retriever, NestedRunKnot):
    """Recall every :class:`MemoryRecord` a writer knot has produced, via lineage."""

    def __init__(
        self,
        *,
        history: Knot | RunHistory,
        data_store: Knot | DataStore,
        writer_knot_id: Knot | str,
        tag_filter: Knot | Mapping[str, Any] | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            history=history,
            data_store=data_store,
            writer_knot_id=writer_knot_id,
            tag_filter=tag_filter,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        history: Any,
        data_store: Any,
        writer_knot_id: str,
        tag_filter: Mapping[str, Any] | None = None,
        **_: Any,
    ) -> list[MemoryRecord]:
        """Return every ``MemoryRecord`` recorded for ``writer_knot_id``, oldest first.

        The lineage query is one call. Fetching the values those rows name is N
        calls, so each is its own
        :class:`~pirn_agents.memory.recalled_lineage_record.RecalledLineageRecord`
        in an inner run — a read gets a ``Result``, a retry, a timeout and a
        lineage row of its own instead of being one turn of a Python loop
        (Rule 11; PIR-874).

        ``history``/``data_store`` are typed ``Any`` here (validated by hand
        below) rather than ``RunHistory``/``DataStore``: neither core type
        mixes in ``PirnOpaqueValue``, so ``Knot._build_adapters`` cannot build
        a ``TypeAdapter`` for them — declaring the real type makes every knot
        construction raise ``PydanticSchemaGenerationError``. No knot in
        ``pirn_agents`` or ``pirn-core`` accepts either type as a ``process()``
        parameter today; this is the first, and the ``Any`` + manual-isinstance
        shape is the workaround until that core gap is closed (candidate
        addition to ADR "agents speaks core" WS0's core-seams list).

        Args:
            history: The ``RunHistory`` the writer knot's runs were recorded to.
            data_store: The ``DataStore`` those runs' outputs were content-
                addressed into.
            writer_knot_id: The ``KnotConfig.id`` of the writer knot whose
                lineage to scan.
            tag_filter: Optional mapping every returned record's ``tags`` must
                be a superset of (e.g. ``{"session_id": "s1"}``). ``None``
                (the default) returns every record the writer knot ever
                produced.

        Returns:
            The recalled records, in the order their lineage rows were
            recorded. Invocations that were skipped or errored, or whose
            value has since been scrubbed or evicted from ``data_store``, are
            silently omitted — recall tolerates gaps, it does not raise for
            them.

        Raises:
            TypeError: If ``history`` is not a ``RunHistory``, ``data_store``
                is not a ``DataStore``, or ``tag_filter`` is not a ``Mapping``
                or ``None``.
            ValueError: If ``writer_knot_id`` is not a non-empty str.
        """
        if not isinstance(history, RunHistory):
            raise TypeError(
                f"MemoryLineageRecall: history must be a RunHistory, got {type(history).__name__}"
            )
        if not isinstance(data_store, DataStore):
            raise TypeError(
                f"MemoryLineageRecall: data_store must be a DataStore, "
                f"got {type(data_store).__name__}"
            )
        if not isinstance(writer_knot_id, str) or not writer_knot_id:
            raise ValueError("MemoryLineageRecall: writer_knot_id must be a non-empty str")
        if tag_filter is not None and not isinstance(tag_filter, Mapping):
            raise TypeError(
                f"MemoryLineageRecall: tag_filter must be a Mapping or None, "
                f"got {type(tag_filter).__name__}"
            )
        rows = await history.query_lineage_by_knot_id(writer_knot_id)
        hashes = [
            row.output_hash for row in rows if row.outcome == "ok" and row.output_hash is not None
        ]
        if not hashes:
            return []
        with Tapestry() as inner:
            store_node = Parameter(
                "data_store", DataStore, default=data_store, _config=KnotConfig(id="data_store")
            )
            per_row: dict[str, Knot] = {
                f"row_{index}": RecalledLineageRecord(
                    data_store=store_node,
                    output_hash=output_hash,
                    tag_filter=tag_filter,
                    _config=KnotConfig(id=f"row_{index}"),
                )
                for index, output_hash in enumerate(hashes)
            }
            Aggregator(
                combine=MemoryLineageRecall._in_row_order,
                _config=KnotConfig(id="recalled"),
                **per_row,
            )
        run = await self._run_inner(inner)
        return run.outputs["recalled"]

    @staticmethod
    def _in_row_order(**rows: MemoryRecord | None) -> list[MemoryRecord]:
        """Put the per-row fetches back in lineage order, dropping the gaps.

        Keys are ``row_<index>``; sorting on the index rather than on the
        mapping's order keeps the result independent of how the engine happened
        to schedule the reads.
        """
        ordered = sorted(rows.items(), key=lambda item: int(item[0].removeprefix("row_")))
        return [record for _key, record in ordered if record is not None]
