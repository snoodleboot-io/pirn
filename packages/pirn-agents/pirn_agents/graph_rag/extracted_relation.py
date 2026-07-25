"""``ExtractedRelation`` — one typed relation produced by schema-guided extraction.

The pydantic unit the F20 structured-output path decodes an LLM's relationship
mentions into. Each relation references two extracted entities by id, carries a
``type`` drawn from the target schema, and optional scalar ``properties``. It
converts one-to-one into a
:class:`~pirn_agents.graph_stores.graph_edge.GraphEdge` at upsert time.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractedRelation(BaseModel):
    """A single typed relation between two extracted entities.

    Attributes
    ----------
    source_id:
        The ``id`` of the source :class:`ExtractedEntity`.
    target_id:
        The ``id`` of the target :class:`ExtractedEntity`.
    type:
        The relation type; must be one of the target schema's relation types.
    properties:
        Optional additional scalar properties.
    """

    source_id: str
    target_id: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
