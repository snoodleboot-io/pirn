"""``ExtractionResult`` — the ``Payload`` an entity/relation extraction hands back.

``ExtractionResult`` is ``Payload[ExtractionFrame, ExtractedGraph]`` (PIR-874,
following the PIR-868 pattern): ``data`` is the
:class:`~pirn_agents.retrieval.graph_rag.extracted_graph.ExtractedGraph` the
structured-output path decoded — the pydantic model that *is* the LLM's schema,
and so stays a plain model — and ``metadata`` is the
:class:`~pirn_agents.retrieval.graph_rag.extraction_frame.ExtractionFrame` with
the counts. A bare decode model crossing the knot boundary carried the entities
and nothing the next knot could trace them back through.
"""

from __future__ import annotations

from typing import Any

from pirn.core.payload import Payload

from pirn_agents.retrieval.graph_rag.extracted_graph import ExtractedGraph
from pirn_agents.retrieval.graph_rag.extraction_frame import ExtractionFrame


class ExtractionResult(Payload[ExtractionFrame, ExtractedGraph]):
    """The decoded graph plus the counts describing it."""

    def __init__(self, graph: ExtractedGraph) -> None:
        frame = ExtractionFrame(
            entity_count=len(graph.entities), relation_count=len(graph.relations)
        )
        super().__init__(metadata=frame, data=graph)

    def _pirn_audit_dict(self) -> dict[str, Any]:
        audit = dict(super()._pirn_audit_dict())
        audit["graph"] = self.data.model_dump()
        return audit

    def __eq__(self, other: object) -> bool:
        """Structural equality: same concrete type, equal metadata and data."""
        if type(other) is not type(self):
            return NotImplemented
        return self._metadata == other._metadata and self._data == other._data
