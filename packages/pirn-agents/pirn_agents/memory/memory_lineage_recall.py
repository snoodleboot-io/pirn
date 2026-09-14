# pyright: reportUnnecessaryIsInstance=false
# runtime-bound knot inputs: explicit type guards are house style (docs/contributing/domain-knots.md)
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
from typing import TYPE_CHECKING, Any

from pirn.backends.base.data_store import DataStore
from pirn.backends.base.run_history import RunHistory
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.interfaces.retriever import Retriever
from pirn_agents.memory.management.memory_record import MemoryRecord

if TYPE_CHECKING:
    from pirn.core.knot_lineage import KnotLineage


class MemoryLineageRecall(Retriever):
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
        rows: list[KnotLineage] = await history.query_lineage_by_knot_id(writer_knot_id)
        records: list[MemoryRecord] = []
        for row in rows:
            if row.outcome != "ok" or row.output_hash is None:
                continue
            try:
                value = await data_store.get(row.output_hash)
            except KeyError:
                continue
            if not isinstance(value, MemoryRecord):
                continue
            if tag_filter is not None and not self._matches(value, tag_filter):
                continue
            records.append(value)
        return records

    @staticmethod
    def _matches(record: MemoryRecord, tag_filter: Mapping[str, Any]) -> bool:
        """True if every ``tag_filter`` entry is present and equal in ``record.tags``."""
        return all(
            record.data.tags.get(key, object()) == value for key, value in tag_filter.items()
        )
