"""``MemoryConsolidator`` — merge near-duplicate episodic records into semantic facts.

The S1 consolidation job. It runs off the hot path (batch/background) over a
supplied batch of episodic
:class:`~pirn_agents.memory_management.memory_record.MemoryRecord`, leaving the
:class:`~pirn_agents.memory_store.MemoryStore` interface unchanged: it only reads
the batch it is given and, optionally, ``store``\\ s the consolidated results.

Pipeline
--------
1. Keep only ``episodic`` records (consolidation is episodic → semantic).
2. Cluster near-duplicates with a
   :class:`~pirn_agents.memory_management.near_duplicate_grouper.NearDuplicateGrouper`.
3. For every group of **two or more** near-duplicates (singletons are already
   clean → left untouched, so clean input is a no-op):

   * resolve the conflict winner via a
     :class:`~pirn_agents.memory_management.conflict_resolution_policy.ConflictResolutionPolicy`
     (default recency/trust) to seed timestamp + trust;
   * summarise the group's contents through the **F17**
     :class:`~pirn_agents.context.summarizer.Summarizer` seam — the same
     provider-neutral compaction interface ``SummaryMemoryCompactor`` uses — into
     one consolidated semantic string;
   * emit a new ``semantic`` record whose provenance ``derivation`` records the
     source ids (an F11-consumable audit trail), and persist it when a store is
     given.

Returns the list of newly created semantic records (empty when nothing merged).
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.summarizer import Summarizer
from pirn_agents.memory_management.conflict_resolution_policy import ConflictResolutionPolicy
from pirn_agents.memory_management.memory_provenance import MemoryProvenance
from pirn_agents.memory_management.memory_record import MemoryRecord
from pirn_agents.memory_management.near_duplicate_grouper import NearDuplicateGrouper
from pirn_agents.memory_management.recency_trust_conflict_policy import RecencyTrustConflictPolicy
from pirn_agents.memory_store import MemoryStore


class MemoryConsolidator(Knot):
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
        """
        if not isinstance(summarizer, Summarizer):
            raise TypeError(
                f"MemoryConsolidator: summarizer must be a Summarizer, "
                f"got {type(summarizer).__name__}"
            )
        grouper = grouper if grouper is not None else NearDuplicateGrouper()
        conflict_policy = (
            conflict_policy if conflict_policy is not None else RecencyTrustConflictPolicy()
        )
        if not isinstance(grouper, NearDuplicateGrouper):
            raise TypeError(
                f"MemoryConsolidator: grouper must be a NearDuplicateGrouper, "
                f"got {type(grouper).__name__}"
            )
        if not isinstance(conflict_policy, ConflictResolutionPolicy):
            raise TypeError(
                f"MemoryConsolidator: conflict_policy must be a ConflictResolutionPolicy, "
                f"got {type(conflict_policy).__name__}"
            )
        if store is not None and not isinstance(store, MemoryStore):
            raise TypeError(
                f"MemoryConsolidator: store must be a MemoryStore or None, "
                f"got {type(store).__name__}"
            )
        episodic = [self._require_record(record) for record in records if record.kind == "episodic"]
        consolidated: list[MemoryRecord] = []
        for group in grouper.group(episodic):
            if len(group) < 2:
                continue
            consolidated.append(await self._consolidate_group(group, summarizer, conflict_policy))
        if store is not None:
            for record in consolidated:
                await store.store(record.id, record.to_payload())
        return consolidated

    @staticmethod
    def _require_record(record: MemoryRecord) -> MemoryRecord:
        """Return ``record`` after asserting it is a :class:`MemoryRecord`."""
        if not isinstance(record, MemoryRecord):
            raise TypeError(
                f"MemoryConsolidator: every record must be a MemoryRecord, "
                f"got {type(record).__name__}"
            )
        return record

    async def _consolidate_group(
        self,
        group: Sequence[MemoryRecord],
        summarizer: Summarizer,
        conflict_policy: ConflictResolutionPolicy,
    ) -> MemoryRecord:
        """Reduce one near-duplicate ``group`` to a single semantic record."""
        winner = conflict_policy.resolve(group)
        summary = await summarizer.summarize([record.content for record in group])
        source_ids = tuple(sorted(record.id for record in group))
        digest = hashlib.sha1(":".join(source_ids).encode("utf-8")).hexdigest()
        provenance = MemoryProvenance(
            source="consolidator",
            timestamp=winner.provenance.timestamp,
            trust_signal=winner.provenance.trust_signal,
            derivation=f"consolidated-from:{','.join(source_ids)}",
        )
        return MemoryRecord(
            id=f"semantic:consolidated:{digest}",
            kind="semantic",
            content=summary,
            provenance=provenance,
            created_at=winner.created_at,
            importance=max(record.importance for record in group),
            last_accessed=None,
            metadata={"source_ids": list(source_ids), "merged_count": len(source_ids)},
        )
