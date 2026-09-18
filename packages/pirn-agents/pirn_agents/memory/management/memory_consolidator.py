"""``MemoryConsolidator`` — merge near-duplicate episodic records into semantic facts.

The S1 consolidation job. It runs off the hot path (batch/background) over a
supplied batch of episodic
:class:`~pirn_agents.memory.management.memory_record.MemoryRecord`, leaving the
:class:`~pirn_agents.memory.stores.memory_store.MemoryStore` interface unchanged: it only reads
the batch it is given and, optionally, ``store``\\ s the consolidated results.

Pipeline
--------
1. Keep only ``episodic`` records (consolidation is episodic → semantic).
2. Cluster near-duplicates with a
   :class:`~pirn_agents.memory.management.near_duplicate_grouper.NearDuplicateGrouper`.
3. For every group of **two or more** near-duplicates (singletons are already
   clean → left untouched, so clean input is a no-op):

   * resolve the conflict winner via a
     :class:`~pirn_agents.memory.management.conflict_resolution_policy.ConflictResolutionPolicy`
     (default recency/trust) to seed timestamp + trust;
   * summarise the group's contents through the **F17**
     :class:`~pirn_agents.context.summarizer.Summarizer` seam — the same
     provider-neutral compaction interface ``SummaryMemoryCompactor`` uses — into
     one consolidated semantic string;
   * emit a new ``semantic`` record whose provenance ``derivation`` records the
     source ids (an F11-consumable audit trail), and persist it when a store is
     given.

Returns the list of newly created semantic records (empty when nothing merged).

One knot per group (PIR-873). The groups are independent of one another, and so
are the store writes, so both are a fan-out and not a sequence: this is a
:class:`~pirn.nodes.nested_run_knot.NestedRunKnot` whose ``process()`` builds one
:class:`~pirn_agents.memory.management.consolidated_memory_group.ConsolidatedMemoryGroup`
per group — followed, when a store is given, by a
:class:`~pirn_agents.memory.management.stored_memory_record.StoredMemoryRecord`
downstream of it — under an :class:`~pirn.nodes.aggregator.Aggregator`, and runs
them through ``_run_inner``. Every summariser call and every write then has its
own lineage row, ``Result``, timeout, retry and admission slot, and the groups
are summarised concurrently under the enclosing run's caps, where the previous
``for group in ...: await summarizer.summarize(...)`` loop serialised every model
call and reported one outcome for the whole batch. As a container this knot holds
no admission slot of its own, so it may not declare a ``concurrency_group``.
Clean input (no group of two or more) starts no inner run.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.nested_run_knot import NestedRunKnot
from pirn.tapestry import Tapestry

from pirn_agents.context.summarizer import Summarizer
from pirn_agents.memory.management.conflict_resolution_policy import ConflictResolutionPolicy
from pirn_agents.memory.management.consolidated_memory_group import ConsolidatedMemoryGroup
from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.management.near_duplicate_grouper import NearDuplicateGrouper
from pirn_agents.memory.management.recency_trust_conflict_policy import RecencyTrustConflictPolicy
from pirn_agents.memory.management.stored_memory_record import StoredMemoryRecord
from pirn_agents.memory.stores.memory_store import MemoryStore


class MemoryConsolidator(NestedRunKnot):
    """Consolidates episodic near-duplicates into deduplicated semantic records."""

    def __init__(
        self,
        *,
        records: Knot | Sequence[MemoryRecord],
        summarizer: Knot | Summarizer,
        grouper: Knot | NearDuplicateGrouper | None = None,
        conflict_policy: Knot | ConflictResolutionPolicy | None = None,
        store: Knot | MemoryStore | None = None,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            records=records,
            summarizer=summarizer,
            grouper=grouper,
            conflict_policy=conflict_policy,
            store=store,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        records: Sequence[MemoryRecord],
        summarizer: Summarizer,
        grouper: NearDuplicateGrouper | None = None,
        conflict_policy: ConflictResolutionPolicy | None = None,
        store: MemoryStore | None = None,
        **_: Any,
    ) -> list[MemoryRecord]:
        """Consolidate ``records`` and return the newly created semantic records.

        Args:
            records: The batch of memory records to consolidate; only episodic
                records participate.
            summarizer: The F17 summarizer that compresses each merged group.
            grouper: Near-duplicate clusterer; defaults to a
                :class:`NearDuplicateGrouper` at threshold ``0.6``.
            conflict_policy: Winner-selection policy; defaults to
                :class:`RecencyTrustConflictPolicy`.
            store: Optional store; when given, each consolidated record is
                persisted under its id.

        Returns:
            The list of consolidated ``semantic`` records (one per merged group).

        Raises:
            TypeError: If ``summarizer``/``grouper``/``conflict_policy``/``store``
                are the wrong type, or any element of ``records`` is not a
                :class:`MemoryRecord`.
            SubTapestryError: If any group's summary or write failed.
        """
        grouper = grouper if grouper is not None else NearDuplicateGrouper()
        conflict_policy = (
            conflict_policy if conflict_policy is not None else RecencyTrustConflictPolicy()
        )
        if store is not None and not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryConsolidator: store must be a MemoryStore or None, "
                f"got {type(store).__name__}"
            )
        episodic = [
            self._require_record(record) for record in records if record.data.kind == "episodic"
        ]
        groups = [tuple(group) for group in grouper.group(episodic) if len(group) >= 2]
        if not groups:
            return []
        return await self._consolidate(groups, summarizer, conflict_policy, store)

    @staticmethod
    def _require_record(record: MemoryRecord) -> MemoryRecord:
        """Return ``record`` after asserting it is a :class:`MemoryRecord`."""
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"MemoryConsolidator: every record must be a MemoryRecord, "
                f"got {type(record).__name__}"
            )
        return record

    async def _consolidate(
        self,
        groups: Sequence[tuple[MemoryRecord, ...]],
        summarizer: Summarizer,
        conflict_policy: ConflictResolutionPolicy,
        store: MemoryStore | None,
    ) -> list[MemoryRecord]:
        """Merge every group as a nested run, one knot per group (plus its write).

        Args:
            groups: The near-duplicate groups, each of two or more records.
            summarizer: The summariser compressing each group.
            conflict_policy: Selects each group's winner.
            store: When given, each consolidated record is written by its own
                knot downstream of the group that produced it.

        Returns:
            The consolidated records, in group order.

        Raises:
            SubTapestryError: If any group's summary or write failed.
        """
        with Tapestry() as inner:
            summarizer_node = Parameter(
                "summarizer", Summarizer, default=summarizer, _config=KnotConfig(id="summarizer")
            )
            policy_node = Parameter(
                "conflict_policy",
                ConflictResolutionPolicy,
                default=conflict_policy,
                _config=KnotConfig(id="conflict_policy"),
            )
            store_node = (
                None
                if store is None
                else Parameter("store", MemoryStore, default=store, _config=KnotConfig(id="store"))
            )
            per_group: dict[str, Knot] = {}
            for index, group in enumerate(groups):
                merged: Knot = ConsolidatedMemoryGroup(
                    group=group,
                    summarizer=summarizer_node,
                    conflict_policy=policy_node,
                    _config=KnotConfig(id=f"group_{index}"),
                )
                per_group[f"group_{index}"] = (
                    merged
                    if store_node is None
                    else StoredMemoryRecord(
                        record=merged,
                        store=store_node,
                        _config=KnotConfig(id=f"stored_{index}"),
                    )
                )
            Aggregator(
                combine=MemoryConsolidator._in_group_order,
                _config=KnotConfig(id="consolidated"),
                **per_group,
            )
        run = await self._run_inner(inner)
        return run.outputs["consolidated"]

    @staticmethod
    def _in_group_order(**merged: MemoryRecord) -> list[MemoryRecord]:
        """Order the consolidated records by their ``group_<index>`` key."""
        return [merged[f"group_{index}"] for index in range(len(merged))]
