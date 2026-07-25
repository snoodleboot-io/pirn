"""``RecencyTrustConflictPolicy`` — most-recent wins, ties broken by trust.

The default, documented conflict-resolution policy for consolidation: the
winning record is the one with the newest
:attr:`MemoryProvenance.timestamp`; when two records share a timestamp the higher
``trust_signal`` wins, and any remaining tie falls back to the higher
``importance`` then the record ``id`` for full determinism. This encodes the
"most-recent, then most-trusted" rule referenced by the F27 design.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn_agents.memory_management.conflict_resolution_policy import ConflictResolutionPolicy
from pirn_agents.memory_management.memory_record import MemoryRecord


class RecencyTrustConflictPolicy(ConflictResolutionPolicy):
    """Resolves conflicts by newest timestamp, then trust, importance, and id."""

    def resolve(self, group: Sequence[MemoryRecord]) -> MemoryRecord:
        """Return the newest / most-trusted record in ``group``.

        Args:
            group: A non-empty sequence of conflicting records.

        Returns:
            The winning :class:`MemoryRecord`.

        Raises:
            ValueError: If ``group`` is empty.
            TypeError: If any element is not a :class:`MemoryRecord`.
        """
        records = tuple(group)
        if not records:
            raise ValueError("RecencyTrustConflictPolicy: group must be non-empty")
        for index, record in enumerate(records):
            if not isinstance(record, MemoryRecord):
                raise TypeError(
                    f"RecencyTrustConflictPolicy: group[{index}] must be a MemoryRecord, "
                    f"got {type(record).__name__}"
                )
        return max(records, key=self._rank)

    @staticmethod
    def _rank(record: MemoryRecord) -> tuple[float, float, float, str]:
        """Return the descending-preference sort key for ``record``."""
        return (
            record.provenance.timestamp.timestamp(),
            float(record.provenance.trust_signal),
            float(record.importance),
            record.id,
        )
