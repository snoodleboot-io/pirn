"""``ExtractionFrame`` — lineage metadata for an :class:`ExtractionResult`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pirn.core.pirn_opaque_value import PirnOpaqueValue


@dataclass(frozen=True)
class ExtractionFrame(PirnOpaqueValue):
    """Run-level facts about one entity/relation extraction.

    The frame half of the ``Payload[ExtractionFrame, ExtractedGraph]`` split
    (PIR-874, following PIR-868): how much the extractor found, as opposed to
    what it found.

    Attributes
    ----------
    entity_count:
        How many entities were extracted.
    relation_count:
        How many relations were extracted.
    """

    entity_count: int
    relation_count: int

    def _pirn_audit_dict(self) -> dict[str, Any]:
        return {"entity_count": self.entity_count, "relation_count": self.relation_count}
