"""``ConsolidatedMemoryGroup`` — merge one near-duplicate group, as its own knot.

Per-group knot of
:class:`~pirn_agents.memory.management.memory_consolidator.MemoryConsolidator`.
Each near-duplicate group is summarised independently of every other, so the
consolidator runs one ``ConsolidatedMemoryGroup`` per group inside a nested run
(:class:`~pirn.nodes.nested_run_knot.NestedRunKnot`) joined by an
:class:`~pirn.nodes.aggregator.Aggregator`: every summariser call gets its own
lineage row, ``Result``, timeout and admission slot, and the groups are
summarised concurrently under the enclosing run's caps instead of one ``await``
at a time inside a single ``process()`` (PIR-873).

Algorithm:
    1. Ask the conflict policy which record of the group wins, seeding the
       merged record's timestamp and trust.
    2. Summarise the group's contents through the ``Summarizer`` seam.
    3. Content-address the sorted source ids through
       :class:`~pirn.core.content_hasher.ContentHasher` for a stable merged id.
    4. Derive a ``semantic`` record from the winner whose provenance names every
       source id and whose importance is the group's maximum.

Internal API.

References:
    pirn-native — no external references.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pirn.core.content_hasher import ContentHasher
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig

from pirn_agents.context.summarizer import Summarizer
from pirn_agents.memory.management.conflict_resolution_policy import ConflictResolutionPolicy
from pirn_agents.memory.management.memory_record import MemoryRecord


class ConsolidatedMemoryGroup(Knot):
    """Reduce one near-duplicate group to a single semantic :class:`MemoryRecord`."""

    def __init__(
        self,
        *,
        group: Knot | Sequence[MemoryRecord],
        summarizer: Knot | Summarizer,
        conflict_policy: Knot | ConflictResolutionPolicy,
        _config: KnotConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            group=group,
            summarizer=summarizer,
            conflict_policy=conflict_policy,
            _config=_config,
            **kwargs,
        )

    async def process(
        self,
        group: Sequence[MemoryRecord],
        summarizer: Summarizer,
        conflict_policy: ConflictResolutionPolicy,
        **_: Any,
    ) -> MemoryRecord:
        """Merge ``group`` into one semantic record.

        Args:
            group: Two or more near-duplicate episodic records.
            summarizer: The summariser compressing the group's contents.
            conflict_policy: Selects the record whose timestamp and trust seed
                the merged one.

        Returns:
            The consolidated ``semantic`` record.

        Raises:
            ValueError: If ``group`` holds fewer than two records — a singleton
                is already clean and is never consolidated.
        """
        records = tuple(group)
        if len(records) < 2:
            raise ValueError(
                f"ConsolidatedMemoryGroup: a group must hold at least two records, "
                f"got {len(records)}"
            )
        winner = conflict_policy.resolve(records)
        summary = await summarizer.summarize([record.data.content for record in records])
        source_ids = tuple(sorted(record.data.id for record in records))
        return winner.derive(
            id=f"semantic:consolidated:{ContentHasher.hash(source_ids)}",
            kind="semantic",
            content=summary,
            source="consolidator",
            derivation=f"consolidated-from:{','.join(source_ids)}",
            importance=max(record.metadata.importance for record in records),
            metadata={"source_ids": list(source_ids), "merged_count": len(source_ids)},
        )
