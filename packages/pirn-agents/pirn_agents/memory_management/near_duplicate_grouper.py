"""``NearDuplicateGrouper`` — cluster near-duplicate records by token overlap.

Consolidation's first step: partition a batch of
:class:`~pirn_agents.memory_management.memory_record.MemoryRecord` into groups of
near-duplicates so each group can collapse to one semantic fact. Similarity is
provider-neutral and pure-python — the Jaccard overlap of case-folded word-token
*sets* — so no embedder or backend is required on the consolidation path:

.. math::

    J(a, b) = \\frac{|T(a) \\cap T(b)|}{|T(a) \\cup T(b)|}

Two records join the same group when ``J`` meets ``threshold``. Grouping is
transitive via union-find: ``a~b`` and ``b~c`` place all three together even if
``a`` and ``c`` alone fall below threshold. Input order is preserved — a group's
records keep their original relative order, and groups are returned ordered by
their earliest member — so consolidation is deterministic.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from pirn.core.pirn_opaque_value import PirnOpaqueValue

from pirn_agents.memory_management.memory_record import MemoryRecord

_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class NearDuplicateGrouper(PirnOpaqueValue):
    """Groups records whose token-set Jaccard similarity meets ``threshold``.

    Attributes
    ----------
    threshold:
        Minimum Jaccard overlap in ``(0, 1]`` for two records to be linked.
    """

    threshold: float = 0.6

    def __post_init__(self) -> None:
        if not isinstance(self.threshold, (int, float)) or isinstance(self.threshold, bool):
            raise TypeError("NearDuplicateGrouper: threshold must be a real number")
        if not 0.0 < float(self.threshold) <= 1.0:
            raise ValueError(
                f"NearDuplicateGrouper: threshold must be in (0, 1], got {self.threshold!r}"
            )

    def group(self, records: Sequence[MemoryRecord]) -> list[list[MemoryRecord]]:
        """Partition ``records`` into near-duplicate groups.

        Args:
            records: The records to cluster.

        Returns:
            A list of groups; each group is a list of records in original order,
            and groups are ordered by their earliest member.

        Raises:
            TypeError: If any element is not a :class:`MemoryRecord`.
        """
        items = tuple(records)
        for index, record in enumerate(items):
            if not isinstance(record, MemoryRecord):
                raise TypeError(
                    f"NearDuplicateGrouper: records[{index}] must be a MemoryRecord, "
                    f"got {type(record).__name__}"
                )
        token_sets = [self._tokenize(record.content) for record in items]
        parent = list(range(len(items)))
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if self._jaccard(token_sets[i], token_sets[j]) >= self.threshold:
                    self._union(parent, i, j)
        groups: dict[int, list[MemoryRecord]] = {}
        for index, record in enumerate(items):
            groups.setdefault(self._find(parent, index), []).append(record)
        return [groups[root] for root in sorted(groups)]

    @staticmethod
    def _tokenize(text: str) -> frozenset[str]:
        """Return the case-folded word-token set of ``text``."""
        return frozenset(_TOKEN.findall(text.lower()))

    @staticmethod
    def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
        """Return the Jaccard similarity of two token sets (``0.0`` when both empty)."""
        if not left and not right:
            return 1.0
        union = left | right
        if not union:
            return 0.0
        return len(left & right) / len(union)

    @staticmethod
    def _find(parent: list[int], node: int) -> int:
        """Return the union-find root of ``node``, compressing the path."""
        root = node
        while parent[root] != root:
            root = parent[root]
        while parent[node] != root:
            parent[node], node = root, parent[node]
        return root

    def _union(self, parent: list[int], left: int, right: int) -> None:
        """Merge the sets containing ``left`` and ``right``, favouring the lower root."""
        left_root = self._find(parent, left)
        right_root = self._find(parent, right)
        if left_root == right_root:
            return
        low, high = sorted((left_root, right_root))
        parent[high] = low
