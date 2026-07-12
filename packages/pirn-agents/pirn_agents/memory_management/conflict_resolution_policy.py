"""``ConflictResolutionPolicy`` — pick the winning record when facts disagree.

Within a near-duplicate group the members may conflict (an updated fact
supersedes an older one). A policy reduces the group to the single record whose
content should represent the consolidated semantic fact. The interface is a
narrow, pluggable seam — concrete policies (recency, trust, source-priority)
override only :meth:`resolve` — mirroring the ``EvictionPolicy`` shape used
elsewhere in the package.
"""

from __future__ import annotations

from collections.abc import Sequence

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_record import MemoryRecord


class ConflictResolutionPolicy(PirnOpaqueValue):
    """Interface for choosing one winning record from a conflicting group."""

    def resolve(self, group: Sequence[MemoryRecord]) -> MemoryRecord:
        """Return the single record that wins ``group``.

        Args:
            group: A non-empty sequence of conflicting/near-duplicate records.

        Returns:
            The winning :class:`MemoryRecord`.
        """
        raise NotImplementedError(f"{type(self).__name__} must implement resolve()")
