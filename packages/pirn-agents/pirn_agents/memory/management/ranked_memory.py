"""``RankedMemory`` — one scored result of ranked recall.

The output unit of :class:`~pirn_agents.memory.management.ranked_recall.RankedRecall`:
the recalled :class:`~pirn_agents.memory.management.memory_record.MemoryRecord`, its
fused composite ``score``, and the three normalised component signals that
produced it. Surfacing the components (not just the total) keeps ranking
explainable and testable.

``RankedMemory`` is ``Payload[RankedMemoryFrame, MemoryRecord]`` (PIR-868 pattern,
enforced by PIR-874): the frame carries the four scores and ``data`` is the
recalled record. It subclasses :class:`pirn.core.payload.Payload` directly, like
``MemoryRecord``, because ``memory/`` must not import from ``specializations/``.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload

from pirn_agents.memory.management.memory_record import MemoryRecord
from pirn_agents.memory.management.ranked_memory_frame import RankedMemoryFrame


class RankedMemory(Payload[RankedMemoryFrame, MemoryRecord]):
    """A recalled record with its composite score and normalised components.

    The constructor takes ``record`` (the recalled memory record), ``score``
    (weighted composite), and the normalised ``relevance``/``recency``/
    ``importance`` signals in ``[0, 1]``. Read back as ``data`` (the record) and
    ``metadata.<signal>``.
    """

    def __init__(
        self,
        record: MemoryRecord,
        score: float,
        relevance: float,
        recency: float,
        importance: float,
    ) -> None:
        frame = RankedMemoryFrame(
            score=score, relevance=relevance, recency=recency, importance=importance
        )
        super().__init__(metadata=frame, data=record)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["record"] = self.data.to_payload()
        return audit

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RankedMemory):
            return NotImplemented
        return self.metadata == other.metadata and self.data == other.data
